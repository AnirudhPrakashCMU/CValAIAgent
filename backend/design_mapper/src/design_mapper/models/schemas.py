from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class AppBaseModel(BaseModel):
    """Base Pydantic model with common configuration."""
    
    model_config = {
        "frozen": False,  # Allow modification for some use cases
        "extra": "forbid",  # Forbid extra fields not defined in the model
        "populate_by_name": True,  # Allow using alias for field names
    }


class MappingRequest(AppBaseModel):
    """
    Input model for requesting design mappings based on brand references and styles.
    This is what the API endpoint will receive as input.
    """
    styles: List[str] = Field(
        default_factory=list,
        description="List of style identifiers (e.g., 'hover_lift', 'pill_button')."
    )
    brand_refs: List[str] = Field(
        default_factory=list,
        description="List of brand references (e.g., 'stripe', 'apple')."
    )
    component: Optional[str] = Field(
        default=None,
        description="Optional component type (e.g., 'button', 'card') for component-specific mappings."
    )
    
    @field_validator('styles', 'brand_refs')
    @classmethod
    def normalize_strings(cls, values: List[str]) -> List[str]:
        """Normalize string values by converting to lowercase and stripping whitespace."""
        return [v.lower().strip() for v in values if v]


class ThemeTokens(AppBaseModel):
    """
    Model representing theme tokens derived from mapping brand references and styles.
    These are abstract design tokens that will be used to generate Tailwind classes.
    """
    # Core visual properties
    primary_color_scheme: Optional[str] = None
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    text_color_primary: Optional[str] = None
    border_color: Optional[str] = None
    
    # Typography
    font_family: Optional[str] = None
    text_style: Optional[str] = None
    
    # Layout & Spacing
    padding: Optional[str] = None
    padding_x: Optional[str] = None
    padding_y: Optional[str] = None
    margin: Optional[str] = None
    margin_x: Optional[str] = None
    margin_y: Optional[str] = None
    
    # Borders & Corners
    border: Optional[str] = None
    border_radius: Optional[str] = None
    border_subtle: Optional[str] = None
    
    # Effects
    shadow: Optional[str] = None
    shadow_subtle: Optional[str] = None
    elevation: Optional[str] = None
    
    # Animations & Interactions
    animation: Optional[str] = None
    animation_ease: Optional[str] = None
    interaction: Optional[str] = None
    
    # Gradients & Advanced Styling
    background_gradient_direction: Optional[str] = None
    acrylic_background: Optional[bool] = None
    ripple_effect: Optional[bool] = None
    utility_driven: Optional[bool] = None
    
    # Component-specific styles (can be extended as needed)
    button_style: Optional[str] = None
    focus_ring: Optional[str] = None
    
    # Catch-all for additional properties not explicitly modeled
    additional_properties: Dict[str, Any] = Field(default_factory=dict)
    
    def update(self, other: 'ThemeTokens') -> 'ThemeTokens':
        """
        Update this ThemeTokens instance with values from another instance.
        Non-None values from 'other' will override values in this instance.
        Returns self for method chaining.
        """
        for field_name, field_value in other.model_dump(exclude_none=True).items():
            if field_name != 'additional_properties':
                setattr(self, field_name, field_value)
            else:
                # For additional_properties, merge rather than replace
                self.additional_properties.update(field_value)
        return self
    
    def to_tailwind_classes(self, token_map: Dict[str, str]) -> List[str]:
        """
        Convert theme tokens to Tailwind CSS classes using the provided token map.
        This is a placeholder implementation - the actual conversion logic would be more complex.
        
        Args:
            token_map: Dictionary mapping token values to Tailwind classes
            
        Returns:
            List of Tailwind CSS classes
        """
        classes = []
        
        # Process explicitly modeled fields
        for field_name, field_value in self.model_dump(exclude_none=True).items():
            if field_name == 'additional_properties':
                continue
                
            # Handle boolean fields
            if isinstance(field_value, bool):
                continue  # Booleans don't directly map to classes
                
            # Handle direct mappings (e.g., primary_color_scheme -> bg-gradient-to-r from-blue-500 to-purple-600)
            if field_value in token_map:
                classes.append(token_map[field_value])
            
            # Handle field-specific mappings
            elif field_name == 'border_radius' and field_value:
                classes.append(f"rounded-{field_value}")
            elif field_name == 'padding' and field_value:
                classes.append(f"{field_value}")
            elif field_name == 'padding_x' and field_value:
                classes.append(f"{field_value}")
            elif field_name == 'padding_y' and field_value:
                classes.append(f"{field_value}")
            elif field_name == 'interaction' and field_value:
                # Interaction might contain multiple classes
                classes.extend(field_value.split())
        
        # Process additional properties
        for key, value in self.additional_properties.items():
            if isinstance(value, str) and value in token_map:
                classes.append(token_map[value])
        
        return classes


class MappingResponse(AppBaseModel):
    """
    Output model for the mapping operation response.
    This is what the API endpoint will return.
    """
    theme_tokens: ThemeTokens = Field(
        default_factory=ThemeTokens,
        description="Theme tokens derived from the mapping operation."
    )
    tailwind_classes: List[str] = Field(
        default_factory=list,
        description="List of Tailwind CSS classes derived from theme tokens."
    )
    source_styles: List[str] = Field(
        default_factory=list,
        description="List of style identifiers that were used in the mapping."
    )
    source_brands: List[str] = Field(
        default_factory=list,
        description="List of brand references that were used in the mapping."
    )


class MappingsData(AppBaseModel):
    """
    Internal model representing the structure of the mappings.json file.
    Used for loading and validating the mappings data.
    """
    brands: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Mapping of brand identifiers to their associated style properties."
    )
    styles: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Mapping of style identifiers to their associated properties."
    )
    tailwind_token_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of abstract tokens to concrete Tailwind classes."
    )


class BrandStyle(AppBaseModel):
    """
    Internal model representing a brand's style properties.
    Used for converting raw JSON data to structured objects.
    """
    brand_id: str = Field(description="Identifier for the brand.")
    properties: Dict[str, Any] = Field(description="Style properties associated with the brand.")


class StyleDefinition(AppBaseModel):
    """
    Internal model representing a style definition.
    Used for converting raw JSON data to structured objects.
    """
    style_id: str = Field(description="Identifier for the style.")
    properties: Dict[str, Any] = Field(description="Properties associated with the style.")


if __name__ == "__main__":
    # Example usage for demonstration
    import json
    
    # Example MappingRequest
    request_example = MappingRequest(
        styles=["hover_lift", "pill_button"],
        brand_refs=["stripe"],
        component="button"
    )
    print("MappingRequest Example:")
    print(json.dumps(request_example.model_dump(), indent=2))
    
    # Example ThemeTokens
    tokens_example = ThemeTokens(
        primary_color_scheme="blue-purple-gradient",
        border_radius="full",
        padding_x="px-6",
        padding_y="py-2",
        interaction="transform transition-transform duration-150 hover:scale-105 hover:shadow-lg"
    )
    print("\nThemeTokens Example:")
    print(json.dumps(tokens_example.model_dump(exclude_none=True), indent=2))
    
    # Example MappingResponse
    response_example = MappingResponse(
        theme_tokens=tokens_example,
        tailwind_classes=[
            "bg-gradient-to-r", "from-blue-500", "to-purple-600",
            "rounded-full", "px-6", "py-2",
            "transform", "transition-transform", "duration-150", "hover:scale-105", "hover:shadow-lg"
        ],
        source_styles=["hover_lift", "pill_button"],
        source_brands=["stripe"]
    )
    print("\nMappingResponse Example:")
    print(json.dumps(response_example.model_dump(exclude_none=True), indent=2))
