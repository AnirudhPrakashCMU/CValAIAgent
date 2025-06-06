from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "demographic_classifier"


settings = Settings()
