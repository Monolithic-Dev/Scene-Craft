from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# agents/.local_storage — local-dev stand-in for Cloud Storage, always
# usable out of the box (unlike the executable-path settings below, a
# storage directory has a meaningful cross-platform default). See
# shared/storage.py.
_DEFAULT_LOCAL_STORAGE_DIR = str(Path(__file__).resolve().parents[1] / ".local_storage")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    # Gemini Developer API — text generation (breakdown_agent) and
    # multimodal captioning (frame_agent), both free-tier friendly.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Vertex AI — frame image generation only. A separate client/mode from
    # the Developer API client above: image generation needs Vertex AI mode
    # (vertexai=True, project, location) since the Developer API's free tier
    # has 0 quota for it — see PHASE-03-FRAME-GENERATION.md and
    # shared/imagen_client.py for why this uses gemini-2.5-flash-image via
    # generate_content rather than the dedicated (deprecated) Imagen
    # generate_images() API. Empty by default: a project without Vertex AI
    # configured just can't generate frames yet, same "stays honestly
    # unconfigured" pattern as mcp_server_python_executable below.
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    imagen_model: str = "gemini-2.5-flash-image"

    # Local-dev stand-in for Cloud Storage (10-DIAGRAMS.md SS9 — frames are
    # meant to live in Cloud Storage in production). Phase 6 swaps this for
    # a real GCS client behind the same store_frame() signature.
    local_storage_dir: str = _DEFAULT_LOCAL_STORAGE_DIR

    # How to reach mcp_server: spawned as a subprocess over stdio, per
    # 03-SYSTEM-DESIGN.md SS2. Empty by default (Windows' Scripts/python.exe
    # vs. Unix's bin/python makes a cross-platform default meaningless) - set
    # explicitly to mcp_server/.venv's interpreter once that venv exists.
    mcp_server_python_executable: str = ""
    mcp_server_working_dir: str = "../mcp_server"


@lru_cache
def get_settings() -> Settings:
    return Settings()
