import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from orchestrator.config import settings
from orchestrator.utils.redis_client import RedisClient
from orchestrator.api.router import router as api_router_v1
from orchestrator.service.websocket import (
    router as websocket_router_v1,
    global_redis_message_handler, # This handler uses the global 'manager' from its own module
)

# Configure logging (already done in config.py, but good to have a logger instance here)
logger = logging.getLogger(settings.SERVICE_NAME + ".main")

# Global Redis client instance, managed by startup/shutdown events
redis_client: RedisClient = RedisClient(config=settings)

# --- OpenAPI Metadata ---
API_TITLE = "MockPilot - Orchestrator Service"
API_VERSION_MAIN = "0.1.0" # Main service version
API_DESCRIPTION = (
    "Handles client WebSocket connections, API requests, "
    "and orchestrates message flow between various backend services via Redis Pub/Sub."
)
API_CONTACT = {
    "name": "MockPilot Development Team",
    "email": "dev@mockpilot.example.com",
}


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application for the Orchestrator service.
    """
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION_MAIN,
        description=API_DESCRIPTION,
        contact=API_CONTACT,
        openapi_url=f"/{settings.API_VERSION}/openapi.json",  # OpenAPI schema URL, prefixed with API version
        docs_url=f"/{settings.API_VERSION}/docs",  # Swagger UI
        redoc_url=f"/{settings.API_VERSION}/redoc",  # ReDoc
        default_response_class=JSONResponse,
    )

    # --- CORS Middleware ---
    if settings.CORS_ALLOWED_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.CORS_ALLOWED_ORIGINS], # Convert AnyHttpUrl to str
            allow_credentials=True,
            allow_methods=["*"],  # Allows all methods
            allow_headers=["*"],  # Allows all headers
        )
        logger.info(f"CORS middleware enabled for origins: {settings.CORS_ALLOWED_ORIGINS}")

    # --- Event Handlers ---
    @app.on_event("startup")
    async def startup_event():
        logger.info(f"Starting {API_TITLE} v{API_VERSION_MAIN}...")
        logger.info(f"Log level set to: {settings.LOG_LEVEL}")

        # Connect to Redis
        if not await redis_client.connect():
            logger.critical("CRITICAL: Failed to connect to Redis during startup. Service may not function correctly.")
            # Depending on requirements, you might want to raise an exception here to stop startup
            # raise RuntimeError("Failed to connect to Redis")
        else:
            logger.info("Successfully connected to Redis.")
            # Start the Redis subscriber for global messages
            if settings.REDIS_SUBSCRIBE_CHANNELS:
                logger.info(f"Starting Redis subscriber for channels: {settings.REDIS_SUBSCRIBE_CHANNELS}")
                # The global_redis_message_handler is imported from websocket.py
                # and uses the ConnectionManager instance also defined in websocket.py
                redis_client.start_subscriber(
                    channels=settings.REDIS_SUBSCRIBE_CHANNELS,
                    message_handler=global_redis_message_handler,
                )
                logger.info("Redis subscriber started.")
            else:
                logger.warning("No Redis channels configured for subscription.")

        # Check JWT Secret Key
        if not settings.JWT_SECRET_KEY or "!!CHANGE_ME_TO_A_STRONG_RANDOM_SECRET_KEY!!" in settings.JWT_SECRET_KEY.get_secret_value():
            logger.critical(
                "CRITICAL: JWT_SECRET_KEY is not set or is using the default placeholder value. "
                "This is insecure and will likely cause authentication failures."
            )
        else:
            logger.info("JWT_SECRET_KEY is configured.")

        logger.info("Orchestrator service startup complete.")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info(f"Shutting down {API_TITLE}...")
        # Stop the Redis subscriber task gracefully
        await redis_client.stop_subscriber_task()
        # Close the Redis connection
        await redis_client.close()
        logger.info("Orchestrator service shutdown complete.")

    # --- Include Routers ---
    # API router (for REST endpoints like /healthz, /sessions)
    # The prefix is already defined in api_router_v1 as /v1
    app.include_router(
        api_router_v1,
        tags=["Orchestrator REST API"],
    )

    # WebSocket router (for /v1/ws/{session_id})
    # The prefix is already defined in websocket_router_v1 as /v1
    app.include_router(
        websocket_router_v1,
        tags=["Orchestrator WebSocket"],
    )

    logger.info(f"FastAPI application configured with API prefix '/{settings.API_VERSION}'.")
    logger.info(f"Access Swagger UI at '/{settings.API_VERSION}/docs'.")
    logger.info(f"Access ReDoc at '/{settings.API_VERSION}/redoc'.")
    return app


# Create the FastAPI app instance using the factory.
# This 'app' instance will be discovered by Uvicorn when running the service.
app = create_app()

if __name__ == "__main__":
    # This block allows running the FastAPI app directly with Uvicorn for development/testing.
    # Example: python -m orchestrator.main
    # Ensure that the PYTHONPATH or current working directory allows importing 'orchestrator'.
    # Typically, you'd run from the `backend/orchestrator/src` directory:
    # `uvicorn orchestrator.main:app --reload --host 0.0.0.0 --port 8000`
    # Or from project root if poetry is set up: `poetry run uvicorn orchestrator.main:app ...`

    import uvicorn

    logger.info("Running Uvicorn directly for Orchestrator development...")
    uvicorn.run(
        "orchestrator.main:app",  # Path to the app instance
        host="0.0.0.0",
        port=8000,  # Default port for orchestrator, can be configured
        log_level=settings.LOG_LEVEL.lower(),
        reload=True, # Enable auto-reload for development
        # workers=1 # For development, 1 worker is fine. For production, adjust.
    )
