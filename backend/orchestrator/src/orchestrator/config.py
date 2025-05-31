import logging
from typing import List, Literal, Optional

from pydantic import AnyHttpUrl, Field, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration settings for the MockPilot Orchestrator service.
    Settings are loaded from environment variables and/or a .env file.
    """

    # --- General Service Settings ---
    SERVICE_NAME: str = Field(default="orchestrator", description="Name of the service.")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level for the service."
    )
    API_VERSION: str = Field(default="v1", description="API version prefix.")

    # --- Redis Settings ---
    REDIS_URL: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="URL for the Redis server instance used for pub/sub and caching.",
    )
    # Channels the orchestrator subscribes to for fanning out to WebSocket clients
    REDIS_SUBSCRIBE_CHANNELS: List[str] = Field(
        default=[
            "transcripts",
            "intents",
            "components", # From Code Generator
            "insights",   # From Sentiment Miner
            "design_specs", # Potentially to inform UI about what's being worked on
            "service_status", # For broadcasting service health/errors
        ],
        description="List of Redis channels the orchestrator subscribes to.",
    )
    # Channel orchestrator might publish to (e.g., client actions back to system)
    # For now, orchestrator primarily relays, but this is a placeholder.
    # REDIS_PUBLISH_CLIENT_ACTIONS_CHANNEL: Optional[str] = Field(
    #     default=None, description="Redis channel for publishing client-originated actions."
    # )


    # --- JWT Authentication Settings ---
    JWT_SECRET_KEY: SecretStr = Field(
        ..., description="Secret key for encoding and decoding JWT tokens. MUST BE SET IN .env."
    )
    JWT_ALGORITHM: str = Field(
        default="HS256", description="Algorithm used for JWT signing."
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60 * 24 * 7,  # 7 days for hackathon convenience
        description="Expiration time for JWT access tokens in minutes.",
    )

    # --- WebSocket Settings ---
    WEBSOCKET_MAX_QUEUE_SIZE: int = Field(
        default=100, description="Maximum number of messages to queue for a WebSocket client before potential backpressure or disconnect."
    )
    WEBSOCKET_HEARTBEAT_INTERVAL_S: float = Field(
        default=25.0, description="Interval in seconds for sending WebSocket ping/heartbeat frames."
    )

    # --- CORS Settings (if serving HTTP routes that need it) ---
    CORS_ALLOWED_ORIGINS: List[AnyHttpUrl] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"], # Default Vite dev server
        description="List of allowed origins for CORS. Use ['*'] for development if needed, but be specific for production.",
    )

    # --- Service Dependencies ---
    # If orchestrator needs to call other services directly via HTTP (not just Redis)
    # Example: SPEECH_TO_TEXT_SERVICE_URL: Optional[AnyHttpUrl] = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",  # Load .env file if present in the orchestrator's CWD or project root
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra environment variables
        case_sensitive=False,
    )


# Initialize settings globally for easy access
# This instance will be populated when the module is imported.
settings = Settings()

# Configure logging based on settings
# Using structlog is recommended for more advanced logging, but basic for now.
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(settings.SERVICE_NAME)

# Log loaded settings (excluding secrets) for verification during startup
# Be careful with logging sensitive information.
startup_log_settings = {
    k: (v.get_secret_value()[:4] + "****" if isinstance(v, SecretStr) else v)
    for k, v in settings.model_dump().items()
}
logger.debug(f"Orchestrator service settings loaded: {startup_log_settings}")

if not settings.JWT_SECRET_KEY or "!!CHANGE_ME_TO_A_STRONG_RANDOM_SECRET_KEY!!" in settings.JWT_SECRET_KEY.get_secret_value():
    logger.critical(
        "CRITICAL: JWT_SECRET_KEY is not set or is using the default placeholder value. "
        "Please set a strong, unique secret in your .env file for JWT_SECRET_KEY."
    )

if __name__ == "__main__":
    # This block allows you to run this file directly to print out the loaded settings
    # Useful for debugging your configuration setup
    print("Loaded Orchestrator Service Settings:")
    for field_name_iter, value_iter in settings.model_dump().items():
        if isinstance(value_iter, SecretStr):
            print(f"  {field_name_iter}: {value_iter.get_secret_value()[:4]}****")
        elif isinstance(value_iter, list) and field_name_iter == "CORS_ALLOWED_ORIGINS":
            print(f"  {field_name_iter}: {[str(url) for url in value_iter]}")
        else:
            print(f"  {field_name_iter}: {value_iter}")
    if "!!CHANGE_ME_TO_A_STRONG_RANDOM_SECRET_KEY!!" in settings.JWT_SECRET_KEY.get_secret_value():
        print("\nWARNING: JWT_SECRET_KEY is using the default placeholder. This is insecure!")
