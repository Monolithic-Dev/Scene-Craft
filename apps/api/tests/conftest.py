import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import Base, get_db
from src.main import _request_log, app


@pytest.fixture()
def client():
    # The in-process rate limiter (main.py) keys on client host, which
    # TestClient reports as a fixed value — without a reset here, every test
    # in the session shares one bucket and later tests start failing with
    # 429s once the cumulative request count crosses the per-minute limit.
    _request_log.clear()

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    credentials = {"email": "priya@example.com", "password": "supersecret1"}
    client.post("/api/v1/auth/signup", json=credentials)
    resp = client.post("/api/v1/auth/login", json=credentials)
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
