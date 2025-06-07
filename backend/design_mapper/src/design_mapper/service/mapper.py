import functools
import logging
from typing import Dict, List, Optional, Set, Tuple, Any

from ..config import settings
from ..models.schemas import (
    MappingRequest,
    MappingResponse,
    ThemeTokens,
)
from ..utils.loader import get_mappings_loader

logger = logging.getLogger(settings.SERVICE_NAME + ".mapper")

# Create a cache decorator if caching is enabled
if settings.ENABLE_LRU_CACHE:
    map_cache = functools.lru_cache(maxsize=settings.LRU_CACHE_MAXSIZE)
else:
    # If caching is disabled, create a no-op decorator
    def map_cache(func):
        return func


def _dict_to_theme_tokens(properties: Dict[str, Any]) -> ThemeTokens:
    """
    Convert a dictionary of properties to a ThemeTokens object.
    
    Args:
        properties: Dictionary of property key-value pairs
        
    Returns:
        ThemeTokens object with properties set
    """
    # Extract known fields that match ThemeTokens model fields
    known_fields = {}
    additional_properties = {}
    
    for key, value in properties.items():
        # Check if this is a field in the ThemeTokens model
        if key in ThemeTokens.model_fields:
            known_fields[key] = value
        else:
            additional_properties[key] = value
    
    # Create ThemeTokens with known fields and add additional properties
    tokens = ThemeTokens(**known_fields, additional_properties=additional_properties)
    return tokens


def _merge_properties_to_tokens(
    brand_properties: List[Dict[str, Any]],
    style_properties: List[Dict[str, Any]],
    component_type: Optional[str] = None
) -> ThemeTokens:
    """
    Merge multiple property dictionaries into a single ThemeTokens object.
    Properties are merged with the following precedence (highest to lowest):
    1. Style properties (later items in list override earlier ones)
    2. Brand properties (later items in list override earlier ones)
    3. Default properties (if any)
    
    Args:
        brand_properties: List of brand property dictionaries
        style_properties: List of style property dictionaries
        component_type: Optional component type for component-specific properties
        
    Returns:
        ThemeTokens object with merged properties
    """
    # Start with an empty ThemeTokens object
    merged_tokens = ThemeTokens()
    
    # Apply brand properties first (in order)
    for props in brand_properties:
        if props:
            brand_tokens = _dict_to_theme_tokens(props)
            merged_tokens.update(brand_tokens)
    
    # Then apply style properties (in order, overriding brand properties)
    for props in style_properties:
        if props:
            style_tokens = _dict_to_theme_tokens(props)
            merged_tokens.update(style_tokens)
    
    # Component-specific overrides are applied in map_request_to_tokens
    
    return merged_tokens


@map_cache
def map_request_to_tokens(request: MappingRequest) -> Tuple[ThemeTokens, List[str], List[str]]:
    """
    Map a MappingRequest to ThemeTokens.
    This function is cached to improve performance for repeated requests.
    
    Args:
        request: MappingRequest containing styles and brand references
        
    Returns:
        Tuple of (ThemeTokens, used_styles, used_brands)
    """
    loader = get_mappings_loader()
    
    # Collect properties from brands
    brand_properties = []
    used_brands = []
    for brand_ref in request.brand_refs:
        brand_props = loader.get_brand_properties(brand_ref)
        if brand_props:
            brand_properties.append(brand_props)
            used_brands.append(brand_ref)
        else:
            logger.warning(f"Brand reference not found in mappings: {brand_ref}")
    
    # Collect properties from styles
    style_properties = []
    used_styles = []
    for style in request.styles:
        style_props = loader.get_style_properties(style)
        if style_props:
            style_properties.append(style_props)
            used_styles.append(style)
        else:
            logger.warning(f"Style not found in mappings: {style}")
        if request.component:
            comp_key = f"{request.component}_{style}"
            comp_props = loader.get_style_properties(comp_key)
            if comp_props:
                style_properties.append(comp_props)
                used_styles.append(comp_key)
    
    # Merge properties into tokens
    tokens = _merge_properties_to_tokens(
        brand_properties,
        style_properties,
        request.component
    )
    
    return tokens, used_styles, used_brands


def _generate_tailwind_classes(tokens: ThemeTokens) -> List[str]:
    """
    Generate Tailwind CSS classes from theme tokens.
    
    Args:
        tokens: ThemeTokens object
        
    Returns:
        List of Tailwind CSS classes
    """
    loader = get_mappings_loader()
    mappings = loader.get_mappings()
    
    if not mappings:
        logger.error("Mappings not available. Cannot generate Tailwind classes.")
        return []
    
    # Get the token map from mappings
    token_map = mappings.tailwind_token_map
    
    # Use the ThemeTokens method to convert to Tailwind classes
    tailwind_classes = tokens.to_tailwind_classes(token_map)
    
    # Process interaction field specially since it often contains multiple classes
    interaction = tokens.interaction
    if interaction:
        # Split the interaction string into individual classes if it contains spaces
        interaction_classes = interaction.split()
        # Add classes that aren't already in the list
        for cls in interaction_classes:
            if cls not in tailwind_classes:
                tailwind_classes.append(cls)
    
    # Remove duplicates while preserving order
    unique_classes: List[str] = []
    seen: Set[str] = set()
    for cls in tailwind_classes:
        if cls not in seen:
            seen.add(cls)
            unique_classes.append(cls)
    
    return unique_classes


def map_request(request: MappingRequest) -> MappingResponse:
    """
    Map a MappingRequest to a MappingResponse.
    This is the main entry point for the mapping service.
    
    Args:
        request: MappingRequest containing styles and brand references
        
    Returns:
        MappingResponse containing theme tokens and Tailwind classes
    """
    logger.info(f"Processing mapping request: styles={request.styles}, brands={request.brand_refs}, component={request.component}")
    
    # Map request to tokens
    tokens, used_styles, used_brands = map_request_to_tokens(request)
    
    # Generate Tailwind classes from tokens
    tailwind_classes = _generate_tailwind_classes(tokens)
    
    # Create and return the response
    response = MappingResponse(
        theme_tokens=tokens,
        tailwind_classes=tailwind_classes,
        source_styles=used_styles,
        source_brands=used_brands
    )
    
    logger.debug(f"Mapping response: {len(tailwind_classes)} classes generated")
    return response


def clear_cache():
    """Clear the mapping cache."""
    if settings.ENABLE_LRU_CACHE:
        map_request_to_tokens.cache_clear()
        logger.info("Mapping cache cleared.")


if __name__ == "__main__":
    # Example usage for testing
    logging.basicConfig(level=logging.DEBUG)
    
    # Example request
    request = MappingRequest(
        styles=["hover_lift", "pill_button"],
        brand_refs=["stripe"],
        component="button"
    )
    
    # Process the request
    response = map_request(request)
    
    # Print the results
    print("Theme Tokens:")
    print(response.theme_tokens.model_dump(exclude_none=True))
    print("\nTailwind Classes:")
    print(response.tailwind_classes)
    print("\nSource Styles:")
    print(response.source_styles)
    print("\nSource Brands:")
    print(response.source_brands)
