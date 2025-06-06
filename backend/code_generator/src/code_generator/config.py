from pydantic import Field, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    SERVICE_NAME: str = "code_generator"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")
    REDIS_DESIGN_SPECS_CHANNEL_NAME: str = Field(default="design_specs")
    REDIS_COMPONENTS_CHANNEL_NAME: str = Field(default="components")
    OPENAI_API_KEY: SecretStr | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

settings = Settings()
