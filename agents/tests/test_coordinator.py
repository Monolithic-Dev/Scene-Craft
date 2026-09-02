"""Covers the [breakdown, frames] plan end to end (mocked agents) —
PHASE-03-FRAME-GENERATION.md SS3 point 4 ("transitions GenerationJob to the
next stage only once every shot has reported complete or failed") and
04-AGENT-ARCHITECTURE.md SS7 point 2 ("fail loud to the Coordinator").
"""
from unittest.mock import patch

from breakdown_agent.agent import BreakdownResult
from frame_agent.agent import FrameGenerationResult
from orchestrator.coordinator import run_initial_generation
from tests.conftest import FakeMcp


async def test_job_status_transitions_through_breakdown_and_frames_to_complete():
    fake_mcp = FakeMcp(script_text="")
    breakdown_result = BreakdownResult(scenes_processed=2, scenes_flagged=0)
    frame_result = FrameGenerationResult(frames_total=3, frames_completed=3, frames_failed=0)

    with (
        patch("orchestrator.coordinator.update_job_status", fake_mcp.update_job_status),
        patch("orchestrator.coordinator.run_breakdown", return_value=breakdown_result),
        patch("orchestrator.coordinator.run_frames", return_value=frame_result),
    ):
        await run_initial_generation("job-1", "proj-1")

    statuses = [entry["status"] for entry in fake_mcp.job_statuses]
    stages = [entry["stage"] for entry in fake_mcp.job_statuses]
    assert statuses == ["running", "running", "running", "complete"]
    assert stages == ["breakdown", "frames", "frames", None]
    # The definitive final progress update carries the real tally regardless
    # of whether any per-shot on_progress callback fired during run_frames.
    final_progress = fake_mcp.job_statuses[2]
    assert final_progress["frames_total"] == 3
    assert final_progress["frames_completed"] == 3
    assert final_progress["frames_failed"] == 0


async def test_frame_agent_progress_callback_is_forwarded_as_status_updates():
    fake_mcp = FakeMcp(script_text="")
    breakdown_result = BreakdownResult(scenes_processed=1, scenes_flagged=0)

    async def _fake_run_frames(project_id, *, on_progress):
        await on_progress(1, 2, 0)
        await on_progress(2, 2, 1)
        return FrameGenerationResult(frames_total=2, frames_completed=2, frames_failed=1)

    with (
        patch("orchestrator.coordinator.update_job_status", fake_mcp.update_job_status),
        patch("orchestrator.coordinator.run_breakdown", return_value=breakdown_result),
        patch("orchestrator.coordinator.run_frames", _fake_run_frames),
    ):
        await run_initial_generation("job-1", "proj-1")

    frame_progress_updates = [
        entry
        for entry in fake_mcp.job_statuses
        if entry["stage"] == "frames" and entry["frames_completed"] is not None
    ]
    assert [u["frames_completed"] for u in frame_progress_updates] == [1, 2, 2]
    assert frame_progress_updates[1]["frames_failed"] == 1


async def test_frame_generation_follows_breakdown_in_orchestrator():
    """Per the state diagram in 10-DIAGRAMS.md SS2 (Breakdown -> FrameGeneration
    only after "shots extracted"): frame generation must not start until
    breakdown has actually returned, not just been scheduled.
    """
    fake_mcp = FakeMcp(script_text="")
    call_order: list[str] = []

    async def _fake_run_breakdown(project_id):
        call_order.append("breakdown")
        return BreakdownResult(scenes_processed=1, scenes_flagged=0)

    async def _fake_run_frames(project_id, *, on_progress):
        call_order.append("frames")
        return FrameGenerationResult(frames_total=0, frames_completed=0, frames_failed=0)

    with (
        patch("orchestrator.coordinator.update_job_status", fake_mcp.update_job_status),
        patch("orchestrator.coordinator.run_breakdown", _fake_run_breakdown),
        patch("orchestrator.coordinator.run_frames", _fake_run_frames),
    ):
        await run_initial_generation("job-1", "proj-1")

    assert call_order == ["breakdown", "frames"]
    assert fake_mcp.job_statuses[-1]["status"] == "complete"


async def test_job_marked_failed_needs_review_when_breakdown_raises():
    fake_mcp = FakeMcp(script_text="")

    async def _raise(project_id: str):
        raise RuntimeError("Gemini call failed twice")

    with (
        patch("orchestrator.coordinator.update_job_status", fake_mcp.update_job_status),
        patch("orchestrator.coordinator.run_breakdown", _raise),
    ):
        await run_initial_generation("job-1", "proj-1")

    assert fake_mcp.job_statuses[0]["status"] == "running"
    assert fake_mcp.job_statuses[0]["stage"] == "breakdown"
    assert fake_mcp.job_statuses[1]["status"] == "failed_needs_review"
    assert "Gemini call failed twice" in fake_mcp.job_statuses[1]["error_detail"]


async def test_job_marked_failed_needs_review_when_frame_generation_raises():
    """A shot-level failure is handled inside frame_agent (placeholder path)
    — this covers a systemic failure (e.g. can't reach project state at
    all), which must still fail the whole job rather than hang at RUNNING.
    """
    fake_mcp = FakeMcp(script_text="")
    breakdown_result = BreakdownResult(scenes_processed=1, scenes_flagged=0)

    async def _raise(project_id: str, *, on_progress):
        raise RuntimeError("mcp_server unreachable mid-fan-out")

    with (
        patch("orchestrator.coordinator.update_job_status", fake_mcp.update_job_status),
        patch("orchestrator.coordinator.run_breakdown", return_value=breakdown_result),
        patch("orchestrator.coordinator.run_frames", _raise),
    ):
        await run_initial_generation("job-1", "proj-1")

    final = fake_mcp.job_statuses[-1]
    assert final["status"] == "failed_needs_review"
    assert "mcp_server unreachable" in final["error_detail"]
    # Never reaches "complete" after a stage failure.
    assert "complete" not in [entry["status"] for entry in fake_mcp.job_statuses]


async def test_never_marks_complete_when_marking_running_fails():
    """If we can't even reach MCP to say RUNNING, don't attempt breakdown at
    all — a job an operator can't see move should never silently proceed.
    """
    from shared.mcp_client import McpClientError

    async def _raise(*args, **kwargs):
        raise McpClientError("mcp_server unreachable")

    with (
        patch("orchestrator.coordinator.update_job_status", _raise),
        patch("orchestrator.coordinator.run_breakdown") as mock_run_breakdown,
        patch("orchestrator.coordinator.run_frames") as mock_run_frames,
    ):
        await run_initial_generation("job-1", "proj-1")

    mock_run_breakdown.assert_not_called()
    mock_run_frames.assert_not_called()
