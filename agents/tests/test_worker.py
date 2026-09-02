"""Covers PHASE-03-FRAME-GENERATION.md SS7's worker-level required tests:
retry/backoff bounds, the placeholder path, and captioning's independent
failure handling.
"""
from unittest.mock import AsyncMock, patch

from frame_agent.worker import (
    _CAPTION_FALLBACK_ALT_TEXT,
    _PLACEHOLDER_ALT_TEXT,
    ShotState,
    generate_frame_for_shot,
)
from shared.gemini_client import GeminiClientError
from shared.imagen_client import ImagenClientError, ImagenNotConfiguredError

_SHOT = ShotState(
    shot_id="shot-1",
    action_summary="Dana stares at the water.",
    suggested_camera="wide",
    location="Ferry deck",
    time_of_day="NIGHT",
    characters=["DANA"],
)


async def test_worker_succeeds_writes_frame_record_with_real_caption():
    with (
        patch("frame_agent.worker.generate_image", return_value=b"png-bytes"),
        patch("frame_agent.worker.store_frame", return_value="file:///shot-1.png") as mock_store,
        patch(
            "frame_agent.worker.generate_alt_text", return_value="Dana stares at the water."
        ),
        patch("frame_agent.worker.write_frame_record", new_callable=AsyncMock) as mock_write,
    ):
        result = await generate_frame_for_shot("proj-1", _SHOT, "neo-noir")

    assert result.succeeded is True
    assert result.needs_review is False
    assert result.image_url == "file:///shot-1.png"
    mock_store.assert_called_once_with("proj-1", "shot-1", b"png-bytes")
    mock_write.assert_called_once_with(
        "shot-1", "file:///shot-1.png", "Dana stares at the water.", needs_review=False
    )


async def test_persistent_imagen_failure_inserts_placeholder():
    with (
        patch("frame_agent.worker.generate_image", side_effect=ImagenClientError("quota")),
        patch("frame_agent.worker.write_frame_record", new_callable=AsyncMock) as mock_write,
        patch("frame_agent.worker.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await generate_frame_for_shot("proj-1", _SHOT, "neo-noir")

    assert result.succeeded is False
    assert result.needs_review is True
    assert result.alt_text == _PLACEHOLDER_ALT_TEXT
    mock_write.assert_called_once_with(
        "shot-1", result.image_url, _PLACEHOLDER_ALT_TEXT, needs_review=True
    )


async def test_not_configured_fails_fast_without_retrying():
    """ImagenNotConfiguredError is a config error, not a transient one —
    retrying it wastes ~3s of backoff per shot for no possible benefit.
    """
    with (
        patch(
            "frame_agent.worker.generate_image",
            side_effect=ImagenNotConfiguredError("google_cloud_project is not set"),
        ) as mock_generate,
        patch("frame_agent.worker.write_frame_record", new_callable=AsyncMock),
        patch("frame_agent.worker.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        result = await generate_frame_for_shot("proj-1", _SHOT, "neo-noir")

    assert mock_generate.call_count == 1
    mock_sleep.assert_not_called()
    assert result.succeeded is False
    assert result.alt_text == _PLACEHOLDER_ALT_TEXT


async def test_retry_backoff_is_exponential_and_bounded():
    attempts = 0

    def _always_fail(prompt):
        nonlocal attempts
        attempts += 1
        raise ImagenClientError("transient")

    sleeps: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    with (
        patch("frame_agent.worker.generate_image", side_effect=_always_fail),
        patch("frame_agent.worker.write_frame_record", new_callable=AsyncMock),
    ):
        result = await generate_frame_for_shot("proj-1", _SHOT, "neo-noir", sleep=_fake_sleep)

    assert attempts == 3
    assert sleeps == [1.0, 2.0]
    assert result.succeeded is False


async def test_caption_failure_does_not_fail_the_shot():
    with (
        patch("frame_agent.worker.generate_image", return_value=b"png-bytes"),
        patch("frame_agent.worker.store_frame", return_value="file:///shot-1.png"),
        patch(
            "frame_agent.worker.generate_alt_text",
            side_effect=GeminiClientError("captioning quota exceeded"),
        ),
        patch("frame_agent.worker.write_frame_record", new_callable=AsyncMock) as mock_write,
    ):
        result = await generate_frame_for_shot("proj-1", _SHOT, "neo-noir")

    # The image itself is still good — a captioning-only failure must not
    # route through the placeholder-image path (PHASE-03-FRAME-GENERATION.md
    # SS5 point 3 / Common Pitfall #4).
    assert result.succeeded is True
    assert result.image_url == "file:///shot-1.png"
    assert result.needs_review is True
    assert result.alt_text == _CAPTION_FALLBACK_ALT_TEXT
    mock_write.assert_called_once_with(
        "shot-1", "file:///shot-1.png", _CAPTION_FALLBACK_ALT_TEXT, needs_review=True
    )


async def test_generate_image_transient_then_success_does_not_flag_the_shot():
    calls = 0

    def _fail_once_then_succeed(prompt):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ImagenClientError("transient")
        return b"png-bytes"

    with (
        patch("frame_agent.worker.generate_image", side_effect=_fail_once_then_succeed),
        patch("frame_agent.worker.store_frame", return_value="file:///shot-1.png"),
        patch("frame_agent.worker.generate_alt_text", return_value="a caption"),
        patch("frame_agent.worker.write_frame_record", new_callable=AsyncMock),
        patch("frame_agent.worker.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await generate_frame_for_shot("proj-1", _SHOT, "neo-noir")

    assert calls == 2
    assert result.succeeded is True
    assert result.needs_review is False
