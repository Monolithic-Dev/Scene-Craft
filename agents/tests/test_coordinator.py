"""test_job_status_transitions_correctly from PHASE-02-BREAKDOWN-AGENT.md SS6
— QUEUED -> RUNNING -> COMPLETE across a real (mocked-LLM) run. QUEUED
itself is apps/api's doing (the job is created there before this process
even starts); the coordinator's own responsibility is RUNNING -> terminal.
"""
from unittest.mock import patch

from breakdown_agent.agent import BreakdownResult
from orchestrator.coordinator import run_initial_generation
from tests.conftest import FakeMcp


async def test_job_status_transitions_running_then_complete_on_success():
    fake_mcp = FakeMcp(script_text="")
    result = BreakdownResult(scenes_processed=2, scenes_flagged=0)

    with (
        patch("orchestrator.coordinator.update_job_status", fake_mcp.update_job_status),
        patch("orchestrator.coordinator.run_breakdown", return_value=result),
    ):
        await run_initial_generation("job-1", "proj-1")

    assert fake_mcp.job_statuses == [("running", None), ("complete", None)]


async def test_job_marked_failed_needs_review_when_breakdown_raises():
    fake_mcp = FakeMcp(script_text="")

    async def _raise(project_id: str):
        raise RuntimeError("Gemini call failed twice")

    with (
        patch("orchestrator.coordinator.update_job_status", fake_mcp.update_job_status),
        patch("orchestrator.coordinator.run_breakdown", _raise),
    ):
        await run_initial_generation("job-1", "proj-1")

    assert fake_mcp.job_statuses[0] == ("running", None)
    assert fake_mcp.job_statuses[1][0] == "failed_needs_review"
    assert "Gemini call failed twice" in fake_mcp.job_statuses[1][1]


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
    ):
        await run_initial_generation("job-1", "proj-1")

    mock_run_breakdown.assert_not_called()
