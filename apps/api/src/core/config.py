"""Application configuration, loaded from environment variables.

In production, these values are injected via Cloud Run environment
configuration backed by Secret Manager — never committed, never hardcoded.
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Convenient for local dev; must never reach a non-development environment.
_INSECURE_DEFAULT_JWT_SECRET = "CHANGE_ME_IN_PRODUCTION_VIA_SECRET_MANAGER"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    # Database — Cloud SQL Postgres in staging/prod, local Postgres/SQLite in dev.
    database_url: str = "sqlite:///./scenecraft.db"

    # Auth
    jwt_secret_key: str = _INSECURE_DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Uploads
    max_script_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_script_pages: int = 50

    # Rate limiting
    rate_limit_requests_per_minute: int = 60

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def _forbid_insecure_jwt_secret_outside_dev(self) -> "Settings":
        is_insecure = self.jwt_secret_key == _INSECURE_DEFAULT_JWT_SECRET
        if self.environment != "development" and is_insecure:
            raise ValueError(
                "jwt_secret_key is still the insecure placeholder value. Set a real "
                "secret via Secret Manager before starting outside 'development'."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
