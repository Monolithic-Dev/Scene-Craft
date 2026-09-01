import io


def _create_project(client, auth_headers) -> str:
    resp = client.post("/api/v1/projects", json={"title": "Midnight Ferry"}, headers=auth_headers)
    return resp.json()["id"]


def test_upload_text_script(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    file_content = b"INT. FERRY - NIGHT\n\nDANA stares out at the water."
    resp = client.post(
        f"/api/v1/projects/{project_id}/scripts",
        files={"file": ("script.txt", io.BytesIO(file_content), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_format"] == "text"
    assert body["project_id"] == project_id
    assert body["job_id"] is not None  # Phase 2: every upload enqueues a generation job


def test_upload_empty_script_is_rejected(client, auth_headers):
    project_id = _create_project(client, auth_headers)
    resp = client.post(
        f"/api/v1/projects/{project_id}/scripts",
        files={"file": ("empty.txt", io.BytesIO(b"   "), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_to_nonexistent_project_is_not_found(client, auth_headers):
    resp = client.post(
        "/api/v1/projects/does-not-exist/scripts",
        files={"file": ("script.txt", io.BytesIO(b"some content"), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_upload_requires_auth(client):
    resp = client.post(
        "/api/v1/projects/some-id/scripts",
        files={"file": ("script.txt", io.BytesIO(b"some content"), "text/plain")},
    )
    assert resp.status_code == 401
