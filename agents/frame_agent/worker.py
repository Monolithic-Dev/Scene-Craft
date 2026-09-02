"""Per-shot fan-out unit (PHASE-03-FRAME-GENERATION.md SS3 point 3). In
production this is one Cloud Run job invocation per shot, triggered by a
Pub/Sub message; the local-dev stand-in (frame_agent/agent.py) runs one of
these coroutines per shot concurrently via asyncio.gather within a single
subprocess instead — see agent.py's module docstring for why that's still
genuine concurrency and not a serial loop wearing async syntax.

Each worker owns its own MCP write: on success or on persistent failure, it
calls write_frame_record itself rather than returning data for something
else to persist — matching the real design where independent Cloud Run jobs
each write their own result with no shared coordinator in the write path.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from frame_agent.captioning import generate_alt_text
from frame_agent.prompts import build_frame_prompt
from shared.gemini_client import GeminiClientError
from shared.imagen_client import ImagenClientError, generate_image
from shared.mcp_client import write_frame_record
from shared.storage import store_frame

logger = logging.getLogger("scenecraft.frame_agent")

# max 3 attempts, exponential backoff — PHASE-03-FRAME-GENERATION.md SS5.
_MAX_ATTEMPTS = 3
_INITIAL_BACKOFF_SECONDS = 1.0

_PLACEHOLDER_IMAGE_URL = "static://frame-unavailable.png"
_PLACEHOLDER_ALT_TEXT = "Storyboard frame generation failed for this shot"
_CAPTION_FALLBACK_ALT_TEXT = (
    "Storyboard frame generated; automatic caption unavailable — flagged for review"
)

SleepFn = Callable[[float], Awaitable[None]]


@dataclass
class ShotState:
    shot_id: str
    action_summary: str
    suggested_camera: str
    location: str
    time_of_day: str
    characters: list[str]


@dataclass
class WorkerResult:
    shot_id: str
    image_url: str
    alt_text: str
    needs_review: bool
    # False only when Imagen generation itself failed persistently (the
    # placeholder path) — a captioning-only failure still counts as
    # succeeded=True, since the image itself is usable
    # (PHASE-03-FRAME-GENERATION.md SS5 point 3).
    succeeded: bool


async def _generate_image_with_retry(prompt: str, *, sleep: SleepFn) -> bytes | None:
    delay = _INITIAL_BACKOFF_SECONDS
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            # generate_images() is a blocking SDK call; to_thread keeps the
            # fan-out in agent.py genuinely concurrent instead of serializing
            # every shot on the single event loop thread.
            return await asyncio.to_thread(generate_image, prompt)
        except ImagenClientError as exc:
            logger.warning(
                "frame_agent.imagen_attempt_failed", extra={"attempt": attempt, "error": str(exc)}
            )
            if attempt == _MAX_ATTEMPTS:
                return None
            await sleep(delay)
            delay *= 2
    return None


async def generate_frame_for_shot(
    project_id: str,
    shot: ShotState,
    style_reference: str | None,
    *,
    sleep: SleepFn = asyncio.sleep,
) -> WorkerResult:
    prompt = build_frame_prompt(
        action_summary=shot.action_summary,
        suggested_camera=shot.suggested_camera,
        location=shot.location,
        time_of_day=shot.time_of_day,
        characters=shot.characters,
        style_reference=style_reference,
    )

    image_bytes = await _generate_image_with_retry(prompt, sleep=sleep)
    if image_bytes is None:
        await write_frame_record(
            shot.shot_id, _PLACEHOLDER_IMAGE_URL, _PLACEHOLDER_ALT_TEXT, needs_review=True
        )
        return WorkerResult(
            shot_id=shot.shot_id,
            image_url=_PLACEHOLDER_IMAGE_URL,
            alt_text=_PLACEHOLDER_ALT_TEXT,
            needs_review=True,
            succeeded=False,
        )

    image_url = store_frame(project_id, shot.shot_id, image_bytes)

    try:
        alt_text = await asyncio.to_thread(generate_alt_text, image_bytes)
        needs_review = False
    except GeminiClientError as exc:
        # Independent failure mode from generation itself — the image is
        # still good, only the caption call broke, so this must not fall
        # into the placeholder-image path.
        logger.warning(
            "frame_agent.captioning_failed", extra={"shot_id": shot.shot_id, "error": str(exc)}
        )
        alt_text = _CAPTION_FALLBACK_ALT_TEXT
        needs_review = True

    await write_frame_record(shot.shot_id, image_url, alt_text, needs_review=needs_review)
    return WorkerResult(
        shot_id=shot.shot_id,
        image_url=image_url,
        alt_text=alt_text,
        needs_review=needs_review,
        succeeded=True,
    )
