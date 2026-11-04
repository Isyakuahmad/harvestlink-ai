from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "HarvestLink AI"
    environment: str = "development"
    debug: bool = False
    database_url: str = "sqlite:///./harvestlink.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    cors_origins: str = "http://localhost:3000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
