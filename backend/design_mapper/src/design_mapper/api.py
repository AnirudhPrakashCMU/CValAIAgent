import logging

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .models.schemas import MappingRequest, MappingResponse
from .service.mapper import map_request, clear_cache
from .utils.loader import get_mappings_loader

logger = logging.getLogger(settings.SERVICE_NAME + ".api")

# Create a router for the mapping endpoint
router = APIRouter(prefix=f"/{settings.API_VERSION}")


@router.post(
    "/map",
    response_model=MappingResponse,
    summary="Map brand references and styles to theme tokens",
    description="Takes a set of style identifiers and brand references and returns the corresponding theme tokens and Tailwind CSS classes.",
)
async def map_design_tokens(request: MappingRequest) -> MappingResponse:
    """
    Map brand references and styles to theme tokens and Tailwind classes.
    
    Args:
        request: MappingRequest containing styles and brand references
        
    Returns:
        MappingResponse containing theme tokens and Tailwind classes
    """
    logger.info(f"Received mapping request: {request.model_dump()}")
    
    try:
        # Process the mapping request
        response = map_request(request)
        return response
    except Exception as e:
        logger.error(f"Error processing mapping request: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing mapping request: {str(e)}"
        )


@router.post(
    "/reload",
    response_model=dict,
    summary="Reload mappings from file",
    description="Force a reload of the mappings file and clear the mapping cache.",
)
async def reload_mappings() -> dict:
    """
    Reload the mappings file and clear the mapping cache.
    
    Returns:
        Dictionary with reload status
    """
    logger.info("Received request to reload mappings")
    
    try:
        # Get the loader and reload mappings
        loader = get_mappings_loader()
        success = loader.load_mappings()
        
        # Clear the mapping cache
        clear_cache()
        
        if success:
            return {"status": "success", "message": "Mappings reloaded successfully"}
        else:
            return {"status": "error", "message": "Failed to reload mappings"}
    except Exception as e:
        logger.error(f"Error reloading mappings: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error reloading mappings: {str(e)}"
        )


@router.get(
    "/healthz",
    response_model=dict,
    summary="Health check endpoint",
    description="Returns the health status of the Design Mapper service.",
)
async def health_check() -> dict:
    """
    Health check endpoint.
    
    Returns:
        Dictionary with service status
    """
    # Check if mappings are loaded
    loader = get_mappings_loader()
    mappings = loader.get_mappings()
    
    if mappings:
        return {
            "status": "ok",
            "service": settings.SERVICE_NAME,
            "mappings_loaded": True,
            "brands_count": len(mappings.brands),
            "styles_count": len(mappings.styles),
            "token_map_count": len(mappings.tailwind_token_map),
        }
    else:
        return {
            "status": "degraded",
            "service": settings.SERVICE_NAME,
            "mappings_loaded": False,
            "message": "Mappings not loaded",
        }


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application for the Design Mapper service.
    
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="MockPilot - Design Mapper Service",
        description="Maps brand references and style cues to theme tokens and Tailwind CSS classes.",
        version="0.1.0",
        docs_url=f"/{settings.API_VERSION}/docs",
        redoc_url=f"/{settings.API_VERSION}/redoc",
        openapi_url=f"/{settings.API_VERSION}/openapi.json",
    )
    
    # Add CORS middleware if needed
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Adjust for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include the router
    app.include_router(router, tags=["Design Mapper"])
    
    # Add startup and shutdown events
    @app.on_event("startup")
    async def startup_event():
        logger.info("Starting Design Mapper service")
        # Ensure mappings are loaded
        loader = get_mappings_loader()
        if not loader.get_mappings():
            logger.warning("Mappings not loaded during startup")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down Design Mapper service")
        # Stop the file watcher
        loader = get_mappings_loader()
        loader.stop_file_watcher()
    
    return app


# Create the FastAPI app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Running Design Mapper API directly")
    uvicorn.run(
        "design_mapper.api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=True,
    )
