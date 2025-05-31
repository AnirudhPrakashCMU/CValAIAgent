import logging
import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, FilePath
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration settings for the MockPilot Design Mapper service.
    Settings are loaded from environment variables and/or a .env file.
    """

    # --- General Service Settings ---
    SERVICE_NAME: str = Field(default="design_mapper", description="Name of the service.")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level for the service."
    )
    API_VERSION: str = Field(default="v1", description="API version prefix for REST endpoints.")

    # --- Mappings File Settings ---
    # Default path is relative to the project root, but can be overridden with an absolute path
    MAPPINGS_FILE_PATH: str = Field(
        default="data/mappings.json",
        description="Path to the JSON file containing brand and style mappings."
    )
    
    # --- File Watcher Settings ---
    ENABLE_HOT_RELOAD: bool = Field(
        default=True,
        description="Whether to watch for changes to the mappings file and reload automatically."
    )
    FILE_WATCH_INTERVAL_SECONDS: float = Field(
        default=2.0,
        description="Interval in seconds for checking if the mappings file has changed."
    )

    # --- Caching Settings ---
    ENABLE_LRU_CACHE: bool = Field(
        default=True,
        description="Whether to cache mapping results using LRU cache."
    )
    LRU_CACHE_MAXSIZE: int = Field(
        default=100,
        description="Maximum number of entries to keep in the LRU cache."
    )

    # --- API Server Settings (for debugging/testing) ---
    API_HOST: str = Field(
        default="0.0.0.0",
        description="Host to bind the API server to."
    )
    API_PORT: int = Field(
        default=8002,  # Different from other services (STT: 8001, Orchestrator: 8000)
        description="Port to bind the API server to."
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",  # Load .env file if present
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra environment variables
        case_sensitive=False,
    )
    
    def get_absolute_mappings_path(self) -> Path:
        """
        Returns the absolute path to the mappings file.
        If MAPPINGS_FILE_PATH is already absolute, it is returned as is.
        Otherwise, it is resolved relative to the project root.
        """
        path = Path(self.MAPPINGS_FILE_PATH)
        if path.is_absolute():
            return path
            
        # If path is relative, resolve it relative to the project root
        # Project root is 3 levels up from this file:
        # backend/design_mapper/src/design_mapper/config.py -> project_root/
        project_root = Path(__file__).resolve().parents[3]
        return project_root / path


# Initialize settings globally for easy access
settings = Settings()

# Configure logging based on settings
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(settings.SERVICE_NAME)

# Log loaded settings for verification during startup
logger.debug(f"Design Mapper service settings loaded: {settings.model_dump()}")
logger.debug(f"Absolute mappings file path: {settings.get_absolute_mappings_path()}")

if __name__ == "__main__":
    # This block allows you to run this file directly to print out the loaded settings
    # Useful for debugging your configuration setup
    print("Loaded Design Mapper Service Settings:")
    for field_name, value in settings.model_dump().items():
        print(f"  {field_name}: {value}")
    
    mappings_path = settings.get_absolute_mappings_path()
    print(f"\nAbsolute mappings file path: {mappings_path}")
    print(f"Mappings file exists: {mappings_path.exists()}")
