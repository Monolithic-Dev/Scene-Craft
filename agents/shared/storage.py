"""Local-dev stand-in for Cloud Storage (10-DIAGRAMS.md SS9: frames belong
in Cloud Storage in production, referenced by URL from Postgres). Writes to
a local directory instead and returns a file:// URL — same class of
local-dev substitution as core/agent_runner.py's subprocess-for-Pub/Sub and
the in-process rate limiter, and the same reason: get the real work (Imagen
calls, retry/placeholder logic, alt-text) fully built and tested now,
without gating all of it on Cloud Storage/IAM provisioning that belongs in
Phase 6 (see docs/Phases/PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md).

Swap point for Phase 6: replace store_frame's body with a real
`storage.Client().bucket(...).blob(...).upload_from_string(...)` call and
return the resulting gs:// or signed HTTPS URL — the function signature and
every caller stay the same.
"""
from pathlib import Path

from shared.config import get_settings


def store_frame(project_id: str, shot_id: str, image_bytes: bytes) -> str:
    settings = get_settings()
    project_dir = Path(settings.local_storage_dir) / "frames" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    file_path = project_dir / f"{shot_id}.png"
    file_path.write_bytes(image_bytes)
    return file_path.resolve().as_uri()
