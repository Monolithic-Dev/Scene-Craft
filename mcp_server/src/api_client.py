"""Thin wrapper around apps/api's /internal/v1 endpoints.

This is the only place in mcp_server that knows about HTTP status codes or
apps/api's URL shape — the tool functions in server.py deal exclusively in
the Pydantic types from schemas.py.
"""
import httpx

from src.config import get_settings
from src.schemas import JobStatusUpdate, ProjectStateSnapshot, SceneInput, WriteResult


class ApiClientError(Exception):
    """Raised when apps/api rejects or fails a request. Message is the
    server's own error detail where available.
    """


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=settings.api_base_url,
        headers={"X-Internal-Service-Key": settings.internal_service_key},
        timeout=settings.request_timeout_seconds,
    )


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    detail = response.text
    try:
        detail = response.json().get("error", {}).get("message", detail)
    except ValueError:
        pass
    raise ApiClientError(f"apps/api returned {response.status_code}: {detail}")


def get_project_state(project_id: str) -> ProjectStateSnapshot:
    with _client() as client:
        response = client.get(f"/internal/v1/projects/{project_id}/state")
    _raise_for_status(response)
    return ProjectStateSnapshot.model_validate(response.json())


def write_shot_records(script_id: str, scenes: list[SceneInput]) -> WriteResult:
    payload = {"scenes": [scene.model_dump() for scene in scenes]}
    with _client() as client:
        response = client.post(f"/internal/v1/scripts/{script_id}/breakdown", json=payload)
    _raise_for_status(response)
    return WriteResult.model_validate(response.json())


def update_job_status(
    job_id: str, status: str, error_detail: str | None = None
) -> JobStatusUpdate:
    payload = {"status": status, "error_detail": error_detail}
    with _client() as client:
        response = client.patch(f"/internal/v1/jobs/{job_id}/status", json=payload)
    _raise_for_status(response)
    return JobStatusUpdate.model_validate(response.json())
