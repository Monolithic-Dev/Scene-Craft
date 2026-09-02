"""Covers PHASE-03-FRAME-GENERATION.md SS7's fan-out/rejoin required tests
at the agent.py level — worker.py's own retry/placeholder/captioning logic
is covered separately in test_worker.py.
"""
import asyncio
from unittest.mock import AsyncMock, patch

from frame_agent.agent import FrameGenerationResult, run
from frame_agent.worker import WorkerResult


def _shot_dict(shot_id: str) -> dict:
    return {
        "id": shot_id,
        "action_summary": "x",
        "suggested_camera": "wide",
        "location": "y",
        "time_of_day": "DAY",
        "characters": [],
    }


def _state(shot_ids: list[str], style_reference: str | None = None) -> dict:
    return {
        "style_reference": style_reference,
        "existing_scenes": [{"shots": [_shot_dict(s) for s in shot_ids]}],
    }


async def test_all_shots_get_a_frame_on_success():
    shot_ids = ["shot-1", "shot-2", "shot-3"]

    async def fake_generate(project_id, shot, style_reference):
        return WorkerResult(
            shot_id=shot.shot_id, image_url="x", alt_text="y", needs_review=False, succeeded=True
        )

    with (
        patch(
            "frame_agent.agent.get_project_state", new=AsyncMock(return_value=_state(shot_ids))
        ),
        patch("frame_agent.agent.generate_frame_for_shot", fake_generate),
    ):
        result = await run("proj-1")

    assert result.frames_total == 3
    assert result.frames_completed == 3
    assert result.frames_failed == 0


async def test_one_failed_shot_does_not_block_others():
    shot_ids = ["shot-1", "shot-2", "shot-3"]

    async def fake_generate(project_id, shot, style_reference):
        succeeded = shot.shot_id != "shot-2"
        return WorkerResult(
            shot_id=shot.shot_id,
            image_url="placeholder" if not succeeded else "x",
            alt_text="y",
            needs_review=not succeeded,
            succeeded=succeeded,
        )

    with (
        patch(
            "frame_agent.agent.get_project_state", new=AsyncMock(return_value=_state(shot_ids))
        ),
        patch("frame_agent.agent.generate_frame_for_shot", fake_generate),
    ):
        result = await run("proj-1")

    assert result.frames_total == 3
    assert result.frames_completed == 3
    assert result.frames_failed == 1


async def test_job_waits_for_all_shots_before_advancing():
    """Progress is monotonic and only reaches total once every shot —
    including the slowest — has actually reported in, regardless of finish
    order (PHASE-03-FRAME-GENERATION.md SS3 point 4).
    """
    shot_ids = ["shot-slow", "shot-fast", "shot-medium"]
    delays = {"shot-slow": 0.06, "shot-fast": 0.01, "shot-medium": 0.03}
    progress_calls: list[tuple[int, int, int]] = []

    async def fake_generate(project_id, shot, style_reference):
        await asyncio.sleep(delays[shot.shot_id])
        return WorkerResult(
            shot_id=shot.shot_id, image_url="x", alt_text="y", needs_review=False, succeeded=True
        )

    async def on_progress(completed: int, total: int, failed: int) -> None:
        progress_calls.append((completed, total, failed))

    with (
        patch(
            "frame_agent.agent.get_project_state", new=AsyncMock(return_value=_state(shot_ids))
        ),
        patch("frame_agent.agent.generate_frame_for_shot", fake_generate),
    ):
        result = await run("proj-1", on_progress=on_progress)

    assert result.frames_completed == 3
    assert [c[0] for c in progress_calls] == [1, 2, 3]
    assert progress_calls[-1] == (3, 3, 0)


async def test_workers_run_concurrently_not_serially():
    """Proves fan-out is real concurrency, not a serial loop wearing async
    syntax — Common Pitfall #1 in PHASE-03-FRAME-GENERATION.md. Each fake
    worker blocks until every worker has started; a serial implementation
    would deadlock here (worker 2 never starts until worker 1 returns, so
    "every worker has started" is never reached) and this test would time out.
    """
    shot_ids = ["shot-1", "shot-2", "shot-3"]
    entered = 0
    lock = asyncio.Lock()
    all_entered = asyncio.Event()

    async def fake_generate(project_id, shot, style_reference):
        nonlocal entered
        async with lock:
            entered += 1
            if entered == len(shot_ids):
                all_entered.set()
        await asyncio.wait_for(all_entered.wait(), timeout=1)
        return WorkerResult(
            shot_id=shot.shot_id, image_url="x", alt_text="y", needs_review=False, succeeded=True
        )

    with (
        patch(
            "frame_agent.agent.get_project_state", new=AsyncMock(return_value=_state(shot_ids))
        ),
        patch("frame_agent.agent.generate_frame_for_shot", fake_generate),
    ):
        result = await asyncio.wait_for(run("proj-1"), timeout=2)

    assert result.frames_completed == 3
    assert entered == 3


async def test_run_with_no_shots_returns_zero_totals_without_calling_workers():
    with (
        patch("frame_agent.agent.get_project_state", new=AsyncMock(return_value=_state([]))),
        patch("frame_agent.agent.generate_frame_for_shot") as mock_generate,
    ):
        result = await run("proj-1")

    assert result == FrameGenerationResult(frames_total=0, frames_completed=0, frames_failed=0)
    mock_generate.assert_not_called()


async def test_run_passes_project_style_reference_to_every_worker():
    shot_ids = ["shot-1", "shot-2"]
    seen_style_refs = []

    async def fake_generate(project_id, shot, style_reference):
        seen_style_refs.append(style_reference)
        return WorkerResult(
            shot_id=shot.shot_id, image_url="x", alt_text="y", needs_review=False, succeeded=True
        )

    with (
        patch(
            "frame_agent.agent.get_project_state",
            new=AsyncMock(return_value=_state(shot_ids, style_reference="neo-noir")),
        ),
        patch("frame_agent.agent.generate_frame_for_shot", fake_generate),
    ):
        await run("proj-1")

    assert seen_style_refs == ["neo-noir", "neo-noir"]
