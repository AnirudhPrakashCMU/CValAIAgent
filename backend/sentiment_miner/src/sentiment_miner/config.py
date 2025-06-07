from pydantic_settings import BaseSettings
from pydantic import RedisDsn


class Settings(BaseSettings):
    SERVICE_NAME: str = "sentiment_miner"
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"
    REDIS_DESIGN_SPECS_CHANNEL_NAME: str = "design_specs"
    REDIS_INSIGHTS_CHANNEL_NAME: str = "insights"


settings = Settings()
