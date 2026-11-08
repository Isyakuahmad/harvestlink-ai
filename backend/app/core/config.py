from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HarvestLink AI"
    environment: str = "development"
    debug: bool = False
    database_url: str = "sqlite:///./harvestlink.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    cors_origins: str = "http://localhost:3000"\n    admin_emails: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
        validate_default=True,
    )

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"development", "test", "staging", "production"}
        if normalized not in allowed:
            raise ValueError(f"environment must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("access_token_expire_minutes")
    @classmethod
    def validate_token_expiry(cls, value: int) -> int:
        if not 1 <= value <= 10080:
            raise ValueError("access_token_expire_minutes must be between 1 and 10080")
        return value

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.environment == "production":
            normalized_secret = self.secret_key.strip().lower()
            unsafe_markers = ("change-me", "replace-with", "your-secret", "example")
            if len(self.secret_key) < 32 or any(
                marker in normalized_secret for marker in unsafe_markers
            ):
                raise ValueError(
                    "production requires a strong SECRET_KEY of at least 32 characters"
                )
            if self.debug:
                raise ValueError("DEBUG must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

