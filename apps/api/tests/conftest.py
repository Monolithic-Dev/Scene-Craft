from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import Base, get_db
from src.core.rate_limiter import RateLimiter
from src.main import app


@pytest.fixture(autouse=True)
def _never_spawn_real_agent_processes():
    """POST /projects/{id}/scripts and POST /projects/{id}/iterate schedule
    trigger_initial_generation_job/trigger_iteration_job as real
    BackgroundTasks, which TestClient executes for real after each response
    — without this, whether a test suite run actually spawns an OS
    subprocess (and what it does) depends on whatever AGENTS_PYTHON_EXECUTABLE
    happens to resolve to in the developer's own .env, which is exactly the
    kind of environment-dependent behavior a test suite must not have.
    Both triggers' own unit tests (test_agent_runner.py) import them
    directly from src.core.agent_runner and are unaffected by this patch,
    which only touches the references api/v1/scripts.py and api/v1/iterate.py hold.
    """
    with (
        patch("src.api.v1.scripts.trigger_initial_generation_job", return_value=False),
        patch("src.api.v1.iterate.trigger_iteration_job", return_value=False),
    ):
        yield


@pytest.fixture()
def client():
    # The Redis-backed rate limiter (core/rate_limiter.py) keys on client
    # host/user id, which TestClient reports as a fixed value per test run —
    # without a fresh fakeredis instance per test, every test in the session
    # would share one bucket and later tests would start failing with 429s
    # once the cumulative request count crosses the per-minute limit.
    app.state.rate_limiter = RateLimiter(client=fakeredis.FakeRedis())

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
