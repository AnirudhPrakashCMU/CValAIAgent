from pydantic_settings import BaseSettings
from pydantic import RedisDsn, AnyUrl

class Settings(BaseSettings):
    SERVICE_NAME: str = "trigger_service"
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"
    REDIS_INTENTS_CHANNEL_NAME: str = "intents"
    REDIS_DESIGN_SPECS_CHANNEL_NAME: str = "design_specs"
    DESIGN_MAPPER_URL: AnyUrl = "http://localhost:8002"
    CONFIDENCE_THRESHOLD: float = 0.75

settings = Settings()
