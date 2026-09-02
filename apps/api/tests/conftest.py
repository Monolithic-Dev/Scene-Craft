from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import Base, get_db
from src.main import _request_log, app


@pytest.fixture(autouse=True)
def _never_spawn_real_agent_processes():
    """POST /projects/{id}/scripts schedules trigger_initial_generation_job
    as a real BackgroundTask, which TestClient executes for real after each
    response — without this, whether a test suite run actually spawns an OS
    subprocess (and what it does) depends on whatever AGENTS_PYTHON_EXECUTABLE
    happens to resolve to in the developer's own .env, which is exactly the
    kind of environment-dependent behavior a test suite must not have.
    trigger_initial_generation_job's own unit tests (test_agent_runner.py)
    import it directly from src.core.agent_runner and are unaffected by this
    patch, which only touches the reference api/v1/scripts.py holds.
    """
    with patch("src.api.v1.scripts.trigger_initial_generation_job", return_value=False):
        yield


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
