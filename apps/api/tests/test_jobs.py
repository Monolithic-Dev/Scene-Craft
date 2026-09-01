import io

from src.core.config import get_settings

settings = get_settings()
_INTERNAL_HEADERS = {"X-Internal-Service-Key": settings.internal_service_key}


def _upload_script(client, auth_headers) -> tuple[str, str]:
    """Returns (project_id, job_id)."""
    project = client.post(
        "/api/v1/projects", json={"title": "Midnight Ferry"}, headers=auth_headers
    ).json()
    file_content = io.BytesIO(b"INT. FERRY - NIGHT\n\nDana waits.")
    script = client.post(
        f"/api/v1/projects/{project['id']}/scripts",
        files={"file": ("script.txt", file_content, "text/plain")},
        headers=auth_headers,
    ).json()
    return project["id"], script["job_id"]


def test_upload_returns_a_pollable_job_id(client, auth_headers):
    _, job_id = _upload_script(client, auth_headers)
    assert job_id is not None


def test_get_job_endpoint_returns_current_status(client, auth_headers):
    _, job_id = _upload_script(client, auth_headers)
    resp = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["steps"] == [{"agent": "breakdown", "status": "queued", "at": None}]


def test_job_status_transitions_are_visible_through_the_api(client, auth_headers):
    _, job_id = _upload_script(client, auth_headers)

    running = client.patch(
        f"/internal/v1/jobs/{job_id}/status", json={"status": "running"}, headers=_INTERNAL_HEADERS
    )
    assert running.status_code == 200
    assert client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers).json()["status"] == "running"

    complete = client.patch(
        f"/internal/v1/jobs/{job_id}/status", json={"status": "complete"}, headers=_INTERNAL_HEADERS
    )
    assert complete.status_code == 200
    final = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers).json()
    assert final["status"] == "complete"
    assert final["steps"][0]["status"] == "complete"


def test_job_failure_carries_error_detail(client, auth_headers):
    _, job_id = _upload_script(client, auth_headers)
    client.patch(
        f"/internal/v1/jobs/{job_id}/status",
        json={"status": "failed_needs_review", "error_detail": "Gemini call failed twice"},
        headers=_INTERNAL_HEADERS,
    )
    body = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers).json()
    assert body["status"] == "failed_needs_review"
    assert body["error_detail"] == "Gemini call failed twice"
    assert body["steps"][0]["status"] == "failed"


def test_get_job_not_found(client, auth_headers):
    resp = client.get("/api/v1/jobs/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404


def test_cannot_access_another_users_job(client, auth_headers):
    _, job_id = _upload_script(client, auth_headers)

    intruder = {"email": "intruder@example.com", "password": "supersecret1"}
    client.post("/api/v1/auth/signup", json=intruder)
    other_token = client.post("/api/v1/auth/login", json=intruder).json()["access_token"]

    resp = client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.status_code == 403


def test_get_job_requires_auth(client):
    resp = client.get("/api/v1/jobs/some-id")
    assert resp.status_code == 401


def test_update_job_status_rejects_unknown_status(client, auth_headers):
    _, job_id = _upload_script(client, auth_headers)
    resp = client.patch(
        f"/internal/v1/jobs/{job_id}/status",
        json={"status": "not_a_real_status"},
        headers=_INTERNAL_HEADERS,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
