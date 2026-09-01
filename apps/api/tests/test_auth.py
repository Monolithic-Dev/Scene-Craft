def test_signup_creates_user(client):
    payload = {"email": "dana@example.com", "password": "supersecret1"}
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "dana@example.com"
    assert "id" in body
    assert "password" not in body
    assert "password_hash" not in body


def test_signup_duplicate_email_is_rejected(client):
    payload = {"email": "dana@example.com", "password": "supersecret1"}
    client.post("/api/v1/auth/signup", json=payload)
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


def test_login_success_returns_token(client):
    payload = {"email": "dana@example.com", "password": "supersecret1"}
    client.post("/api/v1/auth/signup", json=payload)
    resp = client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert len(resp.json()["access_token"]) > 0


def test_login_wrong_password_is_unauthorized(client):
    signup = {"email": "dana@example.com", "password": "supersecret1"}
    client.post("/api/v1/auth/signup", json=signup)
    bad_login = {"email": "dana@example.com", "password": "wrongpass"}
    resp = client.post("/api/v1/auth/login", json=bad_login)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_protected_route_without_token_is_unauthorized(client):
    resp = client.get("/api/v1/projects")
    assert resp.status_code == 401
