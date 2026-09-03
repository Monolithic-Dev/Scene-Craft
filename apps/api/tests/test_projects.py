def test_create_and_list_projects(client, auth_headers):
    resp = client.post(
        "/api/v1/projects",
        json={"title": "Midnight Ferry", "style_reference": "neo-noir, high contrast"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    project = resp.json()
    assert project["title"] == "Midnight Ferry"

    list_resp = client.get("/api/v1/projects", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["projects"]) == 1


def test_get_project_not_found(client, auth_headers):
    resp = client.get("/api/v1/projects/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_cannot_access_another_users_project(client):
    client.post("/api/v1/auth/signup", json={"email": "a@example.com", "password": "supersecret1"})
    token_a = client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "supersecret1"}
    ).json()["access_token"]

    client.post("/api/v1/auth/signup", json={"email": "b@example.com", "password": "supersecret1"})
    token_b = client.post(
        "/api/v1/auth/login", json={"email": "b@example.com", "password": "supersecret1"}
    ).json()["access_token"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    create_resp = client.post("/api/v1/projects", json={"title": "A's Project"}, headers=headers_a)
    project = create_resp.json()

    resp = client.get(f"/api/v1/projects/{project['id']}", headers=headers_b)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_create_project_requires_title(client, auth_headers):
    resp = client.post("/api/v1/projects", json={"title": ""}, headers=auth_headers)
    assert resp.status_code == 422


def test_get_project_has_no_deployed_app_url_before_a_job_sets_it(client, auth_headers):
    project = client.post(
        "/api/v1/projects", json={"title": "Midnight Ferry"}, headers=auth_headers
    ).json()
    resp = client.get(f"/api/v1/projects/{project['id']}", headers=auth_headers)
    assert resp.json()["deployed_app_url"] is None
    assert resp.json()["previs_customization"] is None


def test_get_project_reflects_deployed_app_url_from_latest_job(client, auth_headers):
    import io

    from src.core.config import get_settings

    settings = get_settings()
    internal_headers = {"X-Internal-Service-Key": settings.internal_service_key}

    project = client.post(
        "/api/v1/projects", json={"title": "Midnight Ferry"}, headers=auth_headers
    ).json()
    file_content = io.BytesIO(b"INT. FERRY - NIGHT\n\nDana waits.")
    script = client.post(
        f"/api/v1/projects/{project['id']}/scripts",
        files={"file": ("script.txt", file_content, "text/plain")},
        headers=auth_headers,
    ).json()

    client.patch(
        f"/internal/v1/jobs/{script['job_id']}/status",
        json={
            "status": "running",
            "stage": "app_build",
            "deployed_app_url": f"/projects/{project['id']}/previs",
        },
        headers=internal_headers,
    )
    client.post(
        f"/internal/v1/projects/{project['id']}/previs-customization",
        json={
            "title": "Midnight Ferry",
            "accent_color": "#ff6a00",
            "tone_note": "Tense, nocturnal",
        },
        headers=internal_headers,
    )

    resp = client.get(f"/api/v1/projects/{project['id']}", headers=auth_headers)
    body = resp.json()
    assert body["deployed_app_url"] == f"/projects/{project['id']}/previs"
    assert body["previs_customization"] == {
        "title": "Midnight Ferry",
        "accent_color": "#ff6a00",
        "tone_note": "Tense, nocturnal",
    }


def test_deployed_app_url_survives_a_later_job_that_never_deploys(client, auth_headers):
    """Regression test — caught via a real live-browser check: a later
    iteration job that stops at needs_clarification (or fails before
    app_build) has its own deployed_app_url column at None. GET /projects/{id}
    must still surface the previous job's already-live previs, not lose it
    just because the newest job never got that far.
    """
    import io

    from src.core.config import get_settings

    settings = get_settings()
    internal_headers = {"X-Internal-Service-Key": settings.internal_service_key}

    project = client.post(
        "/api/v1/projects", json={"title": "Midnight Ferry"}, headers=auth_headers
    ).json()
    file_content = io.BytesIO(b"INT. FERRY - NIGHT\n\nDana waits.")
    script = client.post(
        f"/api/v1/projects/{project['id']}/scripts",
        files={"file": ("script.txt", file_content, "text/plain")},
        headers=auth_headers,
    ).json()

    client.patch(
        f"/internal/v1/jobs/{script['job_id']}/status",
        json={
            "status": "complete",
            "stage": "critic",
            "deployed_app_url": f"/projects/{project['id']}/previs",
        },
        headers=internal_headers,
    )

    iterate_job_id = client.post(
        f"/api/v1/projects/{project['id']}/iterate",
        json={"request": "make it darker"},
        headers=auth_headers,
    ).json()["job_id"]
    client.patch(
        f"/internal/v1/jobs/{iterate_job_id}/status",
        json={"status": "needs_clarification", "error_detail": "Which scene did you mean?"},
        headers=internal_headers,
    )

    resp = client.get(f"/api/v1/projects/{project['id']}", headers=auth_headers)
    assert resp.json()["deployed_app_url"] == f"/projects/{project['id']}/previs"
