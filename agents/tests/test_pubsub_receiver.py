"""orchestrator.pubsub_receiver is the Cloud Run entrypoint for deployed
agent workers (see that module's docstring) — a Pub/Sub push subscription
POSTs here instead of apps/api spawning a local subprocess. These tests
post synthetic push envelopes (https://cloud.google.com/pubsub/docs/push's
shape) and assert they route to run_initial_generation/run_iteration.
"""
import base64
import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from orchestrator.pubsub_receiver import app


def _push_envelope(payload: dict) -> dict:
    data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"message": {"data": data, "messageId": "msg-1"}, "subscription": "sub-1"}


def test_healthz():
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_pubsub_push_routes_initial_generation_to_run_initial_generation():
    fake_run = AsyncMock()
    with patch("orchestrator.pubsub_receiver.run_initial_generation", fake_run):
        client = TestClient(app)
        resp = client.post(
            "/pubsub/push",
            json=_push_envelope(
                {"job_type": "initial_generation", "job_id": "job-1", "project_id": "proj-1"}
            ),
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "processed", "job_id": "job-1"}
    fake_run.assert_awaited_once_with("job-1", "proj-1")


def test_pubsub_push_routes_iteration_to_run_iteration():
    fake_run = AsyncMock()
    with patch("orchestrator.pubsub_receiver.run_iteration", fake_run):
        client = TestClient(app)
        resp = client.post(
            "/pubsub/push",
            json=_push_envelope(
                {
                    "job_type": "iteration",
                    "job_id": "job-2",
                    "project_id": "proj-1",
                    "user_request": "make it darker",
                    "requested_by": "user-1",
                }
            ),
        )
    assert resp.status_code == 200
    fake_run.assert_awaited_once_with("job-2", "proj-1", "make it darker", "user-1")


def test_pubsub_push_acks_and_ignores_a_malformed_envelope():
    client = TestClient(app)
    resp = client.post("/pubsub/push", json={"not": "a valid envelope"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored_malformed"
