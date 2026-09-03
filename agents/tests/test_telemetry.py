"""test_agent_span_attributes_present — the required test from
PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md SS9: capture spans emitted
during a real coordinator run (through the existing FakeMcp/fake-agent
fixtures from test_coordinator.py) and assert the required attribute set
from SS1 is present on each one.
"""
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app_build_agent.agent import AppBuildResult
from breakdown_agent.agent import BreakdownResult
from critic_agent.agent import Verdict
from frame_agent.agent import FrameGenerationResult
from orchestrator.coordinator import run_initial_generation
from shared.telemetry import configure_for_testing, reset_for_testing
from tests.conftest import FakeMcp

_BREAKDOWN_OK = BreakdownResult(scenes_processed=2, scenes_flagged=0)
_FRAMES_OK = FrameGenerationResult(frames_total=3, frames_completed=3, frames_failed=0)
_APP_BUILD_OK = AppBuildResult(
    deployed_app_url="/projects/proj-1/previs", used_fallback_customization=False
)
_CRITIC_PASS = Verdict(passed=True)


@pytest.fixture
def span_exporter():
    exporter = InMemorySpanExporter()
    configure_for_testing(exporter)
    yield exporter
    reset_for_testing()


async def _default_run_breakdown(project_id):
    return _BREAKDOWN_OK


async def _default_run_frames(project_id, *, on_progress=None):
    return _FRAMES_OK


async def _default_run_app_build(project_id, *, scoped_shot_ids=None):
    return _APP_BUILD_OK


async def _default_run_critic(project_id, *, scoped_shot_ids=None):
    return _CRITIC_PASS


async def test_agent_span_attributes_present(span_exporter):
    fake_mcp = FakeMcp(script_text="")
    patches = [
        patch("orchestrator.coordinator.update_job_status", fake_mcp.update_job_status),
        patch("orchestrator.coordinator.run_breakdown", _default_run_breakdown),
        patch("orchestrator.coordinator.run_frames", _default_run_frames),
        patch("orchestrator.coordinator.run_app_build", _default_run_app_build),
        patch("orchestrator.coordinator.run_critic", _default_run_critic),
    ]
    for p in patches:
        p.start()
    try:
        await run_initial_generation("job-1", "proj-1")
    finally:
        for p in patches:
            p.stop()

    spans = span_exporter.get_finished_spans()
    span_names = {span.name for span in spans}
    assert span_names == {
        "agent.breakdown.run",
        "agent.frames.run",
        "agent.app_build.run",
        "agent.critic.run",
    }

    required_attrs = {"project_id", "job_id", "agent_name", "status", "duration_ms"}
    for span in spans:
        assert required_attrs.issubset(span.attributes.keys())
        assert span.attributes["project_id"] == "proj-1"
        assert span.attributes["job_id"] == "job-1"
        assert span.attributes["status"] == "success"
        assert isinstance(span.attributes["duration_ms"], float)


async def test_agent_span_marks_failure_and_records_exception(span_exporter):
    fake_mcp = FakeMcp(script_text="")

    async def _failing_run_breakdown(project_id):
        raise RuntimeError("boom")

    patches = [
        patch("orchestrator.coordinator.update_job_status", fake_mcp.update_job_status),
        patch("orchestrator.coordinator.run_breakdown", _failing_run_breakdown),
    ]
    for p in patches:
        p.start()
    try:
        await run_initial_generation("job-1", "proj-1")
    finally:
        for p in patches:
            p.stop()

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "agent.breakdown.run"
    assert span.attributes["status"] == "failure"
    assert len(span.events) == 1  # record_exception() adds one "exception" event
    assert span.events[0].name == "exception"
