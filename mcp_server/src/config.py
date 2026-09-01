from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT = "CHANGE_ME_IN_PRODUCTION_VIA_SECRET_MANAGER"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    api_base_url: str = "http://localhost:8000"
    internal_service_key: str = _INSECURE_DEFAULT
    request_timeout_seconds: float = 30.0

    @model_validator(mode="after")
    def _forbid_insecure_secret_outside_dev(self) -> "Settings":
        if self.environment != "development" and self.internal_service_key == _INSECURE_DEFAULT:
            raise ValueError(
                "internal_service_key is still the insecure placeholder value. Set it to the "
                "same secret apps/api's INTERNAL_SERVICE_KEY uses before starting outside "
                "'development'."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
