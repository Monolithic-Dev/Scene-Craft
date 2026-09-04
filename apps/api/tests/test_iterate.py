import io

from src.core.config import get_settings

settings = get_settings()
_INTERNAL_HEADERS = {"X-Internal-Service-Key": settings.internal_service_key}


def _create_project(client, auth_headers) -> str:
    project = client.post(
        "/api/v1/projects", json={"title": "Midnight Ferry"}, headers=auth_headers
    ).json()
    return project["id"]


def test_iterate_returns_202_and_a_job_id(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    resp = client.post(
        f"/api/v1/projects/{project_id}/iterate",
        json={"request": "make scene 4 night-time"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    assert resp.json()["job_id"]


def test_iterate_job_is_type_iteration_with_the_right_stage_plan(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    job_id = client.post(
        f"/api/v1/projects/{project_id}/iterate",
        json={"request": "make scene 4 night-time"},
        headers=auth_headers,
    ).json()["job_id"]

    body = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers).json()
    assert body["status"] == "queued"
    assert body["steps"] == [
        {
            "agent": "iteration",
            "status": "queued",
            "at": None,
            "completed": None,
            "total": None,
            "failed": None,
        }
    ]


def test_iterate_needs_clarification_status_is_visible_through_the_api(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    job_id = client.post(
        f"/api/v1/projects/{project_id}/iterate",
        json={"request": "make it darker"},
        headers=auth_headers,
    ).json()["job_id"]

    client.patch(
        f"/internal/v1/jobs/{job_id}/status",
        json={
            "status": "needs_clarification",
            "error_detail": "Which scene did you mean?",
        },
        headers=_INTERNAL_HEADERS,
    )

    body = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers).json()
    assert body["status"] == "needs_clarification"
    assert body["error_detail"] == "Which scene did you mean?"
    assert body["steps"][0]["status"] == "needs_clarification"


def test_iterate_rejects_empty_request(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    resp = client.post(
        f"/api/v1/projects/{project_id}/iterate", json={"request": ""}, headers=auth_headers
    )
    assert resp.status_code == 422


def test_iterate_requires_auth(client):
    resp = client.post(
        "/api/v1/projects/does-not-exist/iterate", json={"request": "make it night"}
    )
    assert resp.status_code == 401


def test_iterate_rejects_unowned_project(client, auth_headers):
    project_id = _create_project(client, auth_headers)

    intruder = {"email": "intruder@example.com", "password": "supersecret1"}
    client.post("/api/v1/auth/signup", json=intruder)
    other_token = client.post("/api/v1/auth/login", json=intruder).json()["access_token"]

    resp = client.post(
        f"/api/v1/projects/{project_id}/iterate",
        json={"request": "make it night"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


def test_iterate_rejects_unknown_project(client, auth_headers):
    resp = client.post(
        "/api/v1/projects/does-not-exist/iterate",
        json={"request": "make it night"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_full_generation_then_iteration_stage_plans_do_not_interfere(client, auth_headers):
    """A project's initial_generation job and a later iteration job each
    derive steps from their own job_type — PHASE-05-ITERATION-AND-TRACE-UI.md
    SS5's [iteration, app_build, critic] plan must not bleed into or be
    confused with the [breakdown, frames, app_build, critic] plan.
    """
    project_id = _create_project(client, auth_headers)
    file_content = io.BytesIO(b"INT. FERRY - NIGHT\n\nDana waits.")
    initial_job_id = client.post(
        f"/api/v1/projects/{project_id}/scripts",
        files={"file": ("script.txt", file_content, "text/plain")},
        headers=auth_headers,
    ).json()["job_id"]

    iterate_job_id = client.post(
        f"/api/v1/projects/{project_id}/iterate",
        json={"request": "make it night"},
        headers=auth_headers,
    ).json()["job_id"]

    initial_steps = [
        s["agent"]
        for s in client.get(f"/api/v1/jobs/{initial_job_id}", headers=auth_headers).json()[
            "steps"
        ]
    ]
    iterate_steps = [
        s["agent"]
        for s in client.get(f"/api/v1/jobs/{iterate_job_id}", headers=auth_headers).json()[
            "steps"
        ]
    ]
    assert initial_steps == ["breakdown"]  # queued jobs show only the first stage
    assert iterate_steps == ["iteration"]
