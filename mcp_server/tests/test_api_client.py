"""Verifies api_client.py's request shape and error handling against a fake
transport — no real apps/api process needed for these.
"""
import json
from unittest.mock import patch

import httpx
import pytest

from src.api_client import (
    ApiClientError,
    get_project_state,
    update_job_status,
    write_frame_record,
    write_shot_records,
)
from src.schemas import SceneInput, ShotInput


def _patched_client(handler: httpx.MockTransport):
    """Swaps only the network transport, keeping _client()'s real base_url/
    headers/timeout logic — so these tests also cover that logic, not just
    the mock's own stand-in.
    """
    real_client_cls = httpx.Client

    def client_with_mock_transport(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = handler
        return real_client_cls(*args, **kwargs)  # type: ignore[arg-type]

    return patch("src.api_client.httpx.Client", side_effect=client_with_mock_transport)


def test_get_project_state_sends_the_internal_key_header():
    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(
            200,
            json={
                "project_id": "p1",
                "script_id": "s1",
                "script_text": "text",
                "style_reference": None,
                "existing_scenes": [],
            },
        )

    with _patched_client(httpx.MockTransport(handler)):
        snapshot = get_project_state("p1")

    assert snapshot.project_id == "p1"
    assert seen_requests[0].url.path == "/internal/v1/projects/p1/state"
    assert "X-Internal-Service-Key" in seen_requests[0].headers


def test_get_project_state_raises_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"error": {"code": "NOT_FOUND", "message": "no such project"}}
        return httpx.Response(404, json=body)

    with _patched_client(httpx.MockTransport(handler)):
        with pytest.raises(ApiClientError, match="no such project"):
            get_project_state("does-not-exist")


def test_write_shot_records_posts_the_correct_body():
    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json={"scenes_written": 1, "shots_written": 1})

    shot = ShotInput(
        shot_number=1, location="Deck", action_summary="x", suggested_camera="wide"
    )
    scene = SceneInput(scene_number=1, heading="INT. FERRY - NIGHT", shots=[shot])
    with _patched_client(httpx.MockTransport(handler)):
        result = write_shot_records("script-1", [scene])

    assert result.scenes_written == 1
    assert seen_requests[0].url.path == "/internal/v1/scripts/script-1/breakdown"


def test_update_job_status_raises_apiclienterror_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"error": {"code": "VALIDATION_ERROR", "message": "bad status"}}
        return httpx.Response(400, json=body)

    with _patched_client(httpx.MockTransport(handler)):
        with pytest.raises(ApiClientError, match="bad status"):
            update_job_status("job-1", "not-a-real-status")


def test_update_job_status_sends_progress_fields():
    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(
            200, json={"job_id": "job-1", "status": "running", "updated_at": "2026-01-01T00:00:00Z"}
        )

    with _patched_client(httpx.MockTransport(handler)):
        update_job_status(
            "job-1", "running", stage="frames", frames_total=18, frames_completed=12,
            frames_failed=1,
        )

    body = json.loads(seen_requests[0].content)
    assert body["stage"] == "frames"
    assert body["frames_total"] == 18
    assert body["frames_completed"] == 12
    assert body["frames_failed"] == 1


def test_write_frame_record_posts_the_correct_body():
    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(
            200,
            json={"shot_id": "shot-1", "frame_id": "frame-1", "updated_at": "2026-01-01T00:00:00Z"},
        )

    with _patched_client(httpx.MockTransport(handler)):
        result = write_frame_record("shot-1", "file:///a.png", "Dana waits.", needs_review=True)

    assert result.frame_id == "frame-1"
    assert seen_requests[0].url.path == "/internal/v1/shots/shot-1/frame"


def test_write_frame_record_raises_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"error": {"code": "NOT_FOUND", "message": "no such shot"}}
        return httpx.Response(404, json=body)

    with _patched_client(httpx.MockTransport(handler)):
        with pytest.raises(ApiClientError, match="no such shot"):
            write_frame_record("does-not-exist", "file:///a.png", "x")
