"""Entrypoint: run(project_id, on_progress) -> FrameGenerationResult.

Fan-out execution model (PHASE-03-FRAME-GENERATION.md SS3): in production
this is one Pub/Sub message + Cloud Run job invocation per shot, rejoined by
the Coordinator once every shot reports complete or failed. The local-dev
stand-in is asyncio.gather over one worker.generate_frame_for_shot()
coroutine per shot, all within this single subprocess.

That's a real substitution for "a separate Cloud Run job per shot", but the
concurrency itself is not simulated — every worker's Imagen/captioning call
runs via asyncio.to_thread (see worker.py), so N shots' API calls are
genuinely in flight at once, not serialized behind async syntax. This is
exactly the pitfall PHASE-03-FRAME-GENERATION.md's Common Pitfall #1 warns
about ("generating frames serially 'to keep it simple' ... the single most
common way a hackathon demo times out live") — see
tests/test_frame_agent.py's concurrency test for the proof.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from frame_agent.worker import ShotState, generate_frame_for_shot
from shared.mcp_client import get_project_state

logger = logging.getLogger("scenecraft.frame_agent")

# (completed, total, failed) — "completed" counts every shot that has
# finished processing, success or placeholder; "failed" is the subset of
# those that hit the placeholder path. Matches the {"completed", "total",
# "failed"} shape GET /jobs/{id} reports, per PHASE-03-FRAME-GENERATION.md SS6.
ProgressCallback = Callable[[int, int, int], Awaitable[None]]


@dataclass
class FrameGenerationResult:
    frames_total: int
    frames_completed: int
    frames_failed: int


def _shots_from_state(state: dict[str, Any]) -> list[ShotState]:
    shots = []
    for scene in state.get("existing_scenes", []):
        for shot in scene.get("shots", []):
            shots.append(
                ShotState(
                    shot_id=shot["id"],
                    action_summary=shot["action_summary"],
                    suggested_camera=shot["suggested_camera"],
                    location=shot["location"],
                    time_of_day=shot["time_of_day"],
                    characters=shot.get("characters", []),
                )
            )
    return shots


async def run(
    project_id: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> FrameGenerationResult:
    state = await get_project_state(project_id)
    style_reference = state.get("style_reference")
    shots = _shots_from_state(state)

    total = len(shots)
    completed = 0
    failed = 0
    # Workers finish concurrently (asyncio.gather below); the lock keeps the
    # completed/failed tally — and the on_progress call that reports it —
    # race-free without serializing the actual generation work.
    lock = asyncio.Lock()

    async def _run_one(shot: ShotState) -> None:
        nonlocal completed, failed
        result = await generate_frame_for_shot(project_id, shot, style_reference)
        async with lock:
            completed += 1
            if not result.succeeded:
                failed += 1
            if on_progress is not None:
                await on_progress(completed, total, failed)

    if shots:
        await asyncio.gather(*(_run_one(shot) for shot in shots))

    return FrameGenerationResult(
        frames_total=total, frames_completed=completed, frames_failed=failed
    )
