from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SERVICE_NAME: str = "intent_extractor"
    LOG_LEVEL: str = Field(default="INFO")

    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")
    REDIS_TRANSCRIPTS_CHANNEL_NAME: str = Field(default="transcripts")
    REDIS_INTENTS_CHANNEL_NAME: str = Field(default="intents")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

settings = Settings()
