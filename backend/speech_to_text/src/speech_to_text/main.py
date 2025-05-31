import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import UJSONResponse

from .config import settings
from .service import websocket as stt_websocket_router

# Configure logging (already done in config.py, but good to have a logger instance here)
logger = logging.getLogger(settings.SERVICE_NAME + ".main")

# --- OpenAPI Metadata ---
# This information will be used for the auto-generated OpenAPI documentation (e.g., at /docs)
API_TITLE = "MockPilot - Speech-to-Text Service"
API_VERSION = "0.1.0"
API_DESCRIPTION = (
    "Handles real-time audio transcription using Whisper and Silero VAD. "
    "Provides a WebSocket endpoint to stream audio and receive transcriptions."
)
API_CONTACT = {
    "name": "MockPilot Development Team",
    "email": "dev@mockpilot.example.com",
}


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.
    """
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        contact=API_CONTACT,
        openapi_url="/openapi.json",  # URL for the OpenAPI schema
        docs_url="/docs",  # URL for Swagger UI
        redoc_url="/redoc",  # URL for ReDoc
        default_response_class=UJSONResponse,  # Use UJSON for potentially faster responses
    )

    # --- Event Handlers ---
    @app.on_event("startup")
    async def startup_event():
        logger.info(f"Starting {API_TITLE} v{API_VERSION}...")
        logger.info(f"Log level set to: {settings.LOG_LEVEL}")
        # Perform any other startup tasks here, e.g., initial checks, connecting to global resources.
        # For this service, Redis connections are managed per-websocket connection.
        # A global check for OpenAI API key might be useful.
        if not settings.OPENAI_API_KEY or not settings.OPENAI_API_KEY.get_secret_value():
            logger.critical("CRITICAL: OPENAI_API_KEY is not configured. Service may not function.")
        else:
            logger.info("OpenAI API Key found.")
        logger.info("Speech-to-Text service startup complete.")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info(f"Shutting down {API_TITLE}...")
        # Perform any cleanup tasks here
        logger.info("Speech-to-Text service shutdown complete.")

    # --- Health Check Endpoint ---
    @app.get("/healthz", tags=["Health"], summary="Perform a Health Check")
    async def health_check():
        """
        Simple health check endpoint.
        Returns a 200 OK response if the service is running.
        """
        # Could be expanded to check dependencies (e.g., Redis ping, model load status)
        # For now, a simple "OK" is sufficient.
        return {"status": "ok", "service": API_TITLE, "version": API_VERSION}

    # --- Include Routers ---
    # The WebSocket router from service.websocket handles the /v1/stream endpoint.
    # No additional prefix is added here, so paths are as defined in the router.
    app.include_router(
        stt_websocket_router.router,
        tags=["Speech-to-Text Streaming"],
        # prefix="/api/stt" # Uncomment if you want all STT routes under a common prefix
    )

    logger.info("FastAPI application configured with WebSocket router and health check.")
    return app


# Create the FastAPI app instance using the factory.
# This 'app' instance will be discovered by Uvicorn when running the service.
app = create_app()

if __name__ == "__main__":
    # This block allows running the FastAPI app directly with Uvicorn for development/testing.
    # Example: python -m speech_to_text.main
    # Ensure that the PYTHONPATH or current working directory allows importing 'speech_to_text'.
    # Typically, you'd run from the `backend/speech_to_text/src` directory:
    # `uvicorn speech_to_text.main:app --reload --host 0.0.0.0 --port 8001`
    # Or from project root if poetry is set up: `poetry run uvicorn speech_to_text.main:app ...`

    import uvicorn

    logger.info("Running Uvicorn directly for development...")
    uvicorn.run(
        "speech_to_text.main:app",  # Path to the app instance
        host="0.0.0.0",
        port=8001,  # Example port, can be configured via env var if needed
        log_level=settings.LOG_LEVEL.lower(),
        reload=True, # Enable auto-reload for development
        # workers=1 # For development, 1 worker is fine. For production, adjust.
    )
