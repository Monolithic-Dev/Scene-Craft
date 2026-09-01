from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # How to reach mcp_server: spawned as a subprocess over stdio, per
    # 03-SYSTEM-DESIGN.md SS2. Empty by default (Windows' Scripts/python.exe
    # vs. Unix's bin/python makes a cross-platform default meaningless) - set
    # explicitly to mcp_server/.venv's interpreter once that venv exists.
    mcp_server_python_executable: str = ""
    mcp_server_working_dir: str = "../mcp_server"


@lru_cache
def get_settings() -> Settings:
    return Settings()
