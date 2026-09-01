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

    # Internal API (mcp_server -> apps/api service-to-service calls). A shared
    # secret is the Phase 2-5 local-dev stand-in for the real IAM/mTLS-based
    # service boundary Phase 6 provisions via Terraform — same pattern as the
    # in-process rate limiter flagged in main.py.
    internal_service_key: str = _INSECURE_DEFAULT_JWT_SECRET

    # Uploads
    max_script_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_script_pages: int = 50

    # Rate limiting
    rate_limit_requests_per_minute: int = 60

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Agent orchestration trigger (see core/agent_runner.py). Empty by
    # default: a job stays QUEUED, honestly, until a developer points this
    # at agents/.venv's interpreter (see agents/README or the root README).
    agents_python_executable: str = ""
    agents_working_dir: str = ""

    @model_validator(mode="after")
    def _forbid_insecure_secrets_outside_dev(self) -> "Settings":
        if self.environment == "development":
            return self
        insecure_fields = [
            name
            for name in ("jwt_secret_key", "internal_service_key")
            if getattr(self, name) == _INSECURE_DEFAULT_JWT_SECRET
        ]
        if insecure_fields:
            raise ValueError(
                f"{', '.join(insecure_fields)} still resolve to the insecure placeholder "
                "value. Set real secrets via Secret Manager before starting outside "
                "'development'."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
