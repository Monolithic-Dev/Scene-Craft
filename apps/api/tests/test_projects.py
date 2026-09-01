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
