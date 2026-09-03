"""Covers both job plans end to end (mocked agents):
initial_generation's [breakdown, frames, app_build, critic]
(PHASE-03-FRAME-GENERATION.md SS3 point 4, 04-AGENT-ARCHITECTURE.md SS7
point 2, PHASE-04-APP-BUILD-AND-CRITIC.md SS4/SS6's bounded
one-retry-then-escalate loop) and iteration's
[iteration, app_build (scoped), critic (scoped)]
(PHASE-05-ITERATION-AND-TRACE-UI.md SS3-SS5).
"""
from unittest.mock import patch

from app_build_agent.agent import AppBuildResult
from breakdown_agent.agent import BreakdownResult
from critic_agent.agent import Verdict
from frame_agent.agent import FrameGenerationResult
from iteration_agent.agent import IterationResult
from orchestrator.coordinator import run_initial_generation, run_iteration
from tests.conftest import FakeMcp

_BREAKDOWN_OK = BreakdownResult(scenes_processed=2, scenes_flagged=0)
_FRAMES_OK = FrameGenerationResult(frames_total=3, frames_completed=3, frames_failed=0)
_APP_BUILD_OK = AppBuildResult(
    deployed_app_url="/projects/proj-1/previs", used_fallback_customization=False
)
_CRITIC_PASS = Verdict(passed=True)
_ITERATION_OK = IterationResult(affected_shot_ids=["shot-1"])


async def _default_run_breakdown(project_id):
    return _BREAKDOWN_OK


async def _default_run_frames(project_id, *, on_progress=None):
    return _FRAMES_OK


async def _default_run_app_build(project_id, *, scoped_shot_ids=None):
    return _APP_BUILD_OK


async def _default_run_critic(project_id, *, scoped_shot_ids=None):
    return _CRITIC_PASS


async def _default_run_iteration_agent(project_id, user_request, requested_by):
    return _ITERATION_OK


def _patches(fake_mcp: FakeMcp, **overrides):
    defaults = {
        "orchestrator.coordinator.update_job_status": fake_mcp.update_job_status,
        "orchestrator.coordinator.run_breakdown": _default_run_breakdown,
        "orchestrator.coordinator.run_frames": _default_run_frames,
        "orchestrator.coordinator.run_app_build": _default_run_app_build,
        "orchestrator.coordinator.run_critic": _default_run_critic,
        "orchestrator.coordinator.run_iteration_agent": _default_run_iteration_agent,
    }
    defaults.update(overrides)
    return [patch(target, value) for target, value in defaults.items()]


async def _run_with(fake_mcp: FakeMcp, **overrides) -> None:
    patches = _patches(fake_mcp, **overrides)
    for p in patches:
        p.start()
    try:
        await run_initial_generation("job-1", "proj-1")
    finally:
        for p in patches:
            p.stop()


async def _run_iteration_with(fake_mcp: FakeMcp, **overrides) -> None:
    patches = _patches(fake_mcp, **overrides)
    for p in patches:
        p.start()
    try:
        await run_iteration("job-1", "proj-1", "make scene 4 night-time", "user-1")
    finally:
        for p in patches:
            p.stop()


# --- initial_generation ------------------------------------------------------


async def test_job_status_transitions_through_full_plan_to_complete():
    fake_mcp = FakeMcp(script_text="")
    await _run_with(fake_mcp)

    statuses = [entry["status"] for entry in fake_mcp.job_statuses]
    stages = [entry["stage"] for entry in fake_mcp.job_statuses]
    assert statuses == ["running", "running", "running", "running", "running", "complete"]
    assert stages == ["breakdown", "frames", "frames", "app_build", "critic", None]
    assert fake_mcp.job_statuses[-1]["deployed_app_url"] == "/projects/proj-1/previs"


async def test_frame_agent_progress_callback_is_forwarded_as_status_updates():
    fake_mcp = FakeMcp(script_text="")

    async def _fake_run_frames(project_id, *, on_progress):
        await on_progress(1, 2, 0)
        await on_progress(2, 2, 1)
        return FrameGenerationResult(frames_total=2, frames_completed=2, frames_failed=1)

    await _run_with(fake_mcp, **{"orchestrator.coordinator.run_frames": _fake_run_frames})

    frame_progress_updates = [
        entry
        for entry in fake_mcp.job_statuses
        if entry["stage"] == "frames" and entry["frames_completed"] is not None
    ]
    assert [u["frames_completed"] for u in frame_progress_updates] == [1, 2, 2]
    assert frame_progress_updates[1]["frames_failed"] == 1


async def test_stages_run_in_order():
    """Per the state diagram in 10-DIAGRAMS.md SS2: each stage only starts
    once the previous one has actually returned, not just been scheduled.
    """
    fake_mcp = FakeMcp(script_text="")
    call_order: list[str] = []

    async def _fake_run_breakdown(project_id):
        call_order.append("breakdown")
        return _BREAKDOWN_OK

    async def _fake_run_frames(project_id, *, on_progress):
        call_order.append("frames")
        return _FRAMES_OK

    async def _fake_run_app_build(project_id, *, scoped_shot_ids=None):
        call_order.append("app_build")
        return _APP_BUILD_OK

    async def _fake_run_critic(project_id, *, scoped_shot_ids=None):
        call_order.append("critic")
        return _CRITIC_PASS

    await _run_with(
        fake_mcp,
        **{
            "orchestrator.coordinator.run_breakdown": _fake_run_breakdown,
            "orchestrator.coordinator.run_frames": _fake_run_frames,
            "orchestrator.coordinator.run_app_build": _fake_run_app_build,
            "orchestrator.coordinator.run_critic": _fake_run_critic,
        },
    )

    assert call_order == ["breakdown", "frames", "app_build", "critic"]
    assert fake_mcp.job_statuses[-1]["status"] == "complete"


async def test_job_marked_failed_needs_review_when_breakdown_raises():
    fake_mcp = FakeMcp(script_text="")

    async def _raise(project_id: str):
        raise RuntimeError("Gemini call failed twice")

    await _run_with(fake_mcp, **{"orchestrator.coordinator.run_breakdown": _raise})

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

    async def _raise(project_id: str, *, on_progress):
        raise RuntimeError("mcp_server unreachable mid-fan-out")

    await _run_with(fake_mcp, **{"orchestrator.coordinator.run_frames": _raise})

    final = fake_mcp.job_statuses[-1]
    assert final["status"] == "failed_needs_review"
    assert "mcp_server unreachable" in final["error_detail"]
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
        patch("orchestrator.coordinator.run_app_build") as mock_run_app_build,
        patch("orchestrator.coordinator.run_critic") as mock_run_critic,
    ):
        await run_initial_generation("job-1", "proj-1")

    mock_run_breakdown.assert_not_called()
    mock_run_frames.assert_not_called()
    mock_run_app_build.assert_not_called()
    mock_run_critic.assert_not_called()


async def test_job_marked_failed_needs_review_when_app_build_raises():
    fake_mcp = FakeMcp(script_text="")

    async def _raise(project_id: str, *, scoped_shot_ids=None):
        raise RuntimeError("Gemini quota exhausted")

    await _run_with(fake_mcp, **{"orchestrator.coordinator.run_app_build": _raise})

    final = fake_mcp.job_statuses[-1]
    assert final["status"] == "failed_needs_review"
    assert "Gemini quota exhausted" in final["error_detail"]
    assert "complete" not in [entry["status"] for entry in fake_mcp.job_statuses]


async def test_critic_failure_triggers_exactly_one_app_build_retry_then_succeeds():
    fake_mcp = FakeMcp(script_text="")
    app_build_calls = 0
    critic_calls = 0

    async def _fake_run_app_build(project_id, *, scoped_shot_ids=None):
        nonlocal app_build_calls
        app_build_calls += 1
        return _APP_BUILD_OK

    async def _fake_run_critic(project_id, *, scoped_shot_ids=None):
        nonlocal critic_calls
        critic_calls += 1
        if critic_calls == 1:
            return Verdict(passed=False, missing_shots=["shot-1"], notes="shot-1 missing a frame")
        return Verdict(passed=True)

    await _run_with(
        fake_mcp,
        **{
            "orchestrator.coordinator.run_app_build": _fake_run_app_build,
            "orchestrator.coordinator.run_critic": _fake_run_critic,
        },
    )

    assert app_build_calls == 2
    assert critic_calls == 2
    assert fake_mcp.job_statuses[-1]["status"] == "complete"


async def test_critic_failure_after_retry_marks_needs_review_with_verdict_notes():
    fake_mcp = FakeMcp(script_text="")
    failing_verdict = Verdict(
        passed=False, missing_shots=["shot-1"], notes="shot-1 missing a frame entirely"
    )

    async def _fake_run_critic(project_id, *, scoped_shot_ids=None):
        return failing_verdict

    await _run_with(fake_mcp, **{"orchestrator.coordinator.run_critic": _fake_run_critic})

    final = fake_mcp.job_statuses[-1]
    assert final["status"] == "failed_needs_review"
    assert final["error_detail"] == "shot-1 missing a frame entirely"
    assert "complete" not in [entry["status"] for entry in fake_mcp.job_statuses]


async def test_critic_retry_never_loops_more_than_once():
    """Unbounded retries between Critic and App-Build would burn API budget
    forever on a systematically broken project — exactly the failure mode
    PHASE-04-APP-BUILD-AND-CRITIC.md Common Pitfall #3 warns against.
    """
    fake_mcp = FakeMcp(script_text="")
    critic_calls = 0

    async def _always_fail(project_id, *, scoped_shot_ids=None):
        nonlocal critic_calls
        critic_calls += 1
        return Verdict(passed=False, notes="still broken")

    await _run_with(fake_mcp, **{"orchestrator.coordinator.run_critic": _always_fail})

    assert critic_calls == 2  # initial attempt + exactly one retry, never more


async def test_app_build_result_deployed_app_url_flows_through_to_critic_stage_update():
    fake_mcp = FakeMcp(script_text="")
    custom_result = AppBuildResult(
        deployed_app_url="/projects/proj-1/previs", used_fallback_customization=True
    )

    async def _fake_run_app_build(project_id, *, scoped_shot_ids=None):
        return custom_result

    await _run_with(fake_mcp, **{"orchestrator.coordinator.run_app_build": _fake_run_app_build})

    critic_stage_update = next(e for e in fake_mcp.job_statuses if e["stage"] == "critic")
    assert critic_stage_update["deployed_app_url"] == "/projects/proj-1/previs"


# --- iteration ----------------------------------------------------------------


async def test_iteration_job_status_transitions_through_full_plan_to_complete():
    fake_mcp = FakeMcp(script_text="")
    await _run_iteration_with(fake_mcp)

    statuses = [entry["status"] for entry in fake_mcp.job_statuses]
    stages = [entry["stage"] for entry in fake_mcp.job_statuses]
    assert statuses == ["running", "running", "running", "complete"]
    assert stages == ["iteration", "app_build", "critic", None]
    assert fake_mcp.job_statuses[-1]["deployed_app_url"] == "/projects/proj-1/previs"


async def test_iteration_passes_affected_shot_ids_to_scoped_app_build_and_critic():
    fake_mcp = FakeMcp(script_text="")
    seen_scopes = []

    async def _fake_run_app_build(project_id, *, scoped_shot_ids=None):
        seen_scopes.append(("app_build", scoped_shot_ids))
        return _APP_BUILD_OK

    async def _fake_run_critic(project_id, *, scoped_shot_ids=None):
        seen_scopes.append(("critic", scoped_shot_ids))
        return _CRITIC_PASS

    async def _fake_run_iteration_agent(project_id, user_request, requested_by):
        return IterationResult(affected_shot_ids=["shot-1", "shot-2"])

    await _run_iteration_with(
        fake_mcp,
        **{
            "orchestrator.coordinator.run_app_build": _fake_run_app_build,
            "orchestrator.coordinator.run_critic": _fake_run_critic,
            "orchestrator.coordinator.run_iteration_agent": _fake_run_iteration_agent,
        },
    )

    assert seen_scopes == [
        ("app_build", ["shot-1", "shot-2"]),
        ("critic", ["shot-1", "shot-2"]),
    ]


async def test_iteration_needs_clarification_never_runs_app_build_or_critic():
    fake_mcp = FakeMcp(script_text="")

    async def _fake_run_iteration_agent(project_id, user_request, requested_by):
        return IterationResult(clarification_needed="Which scene did you mean?")

    with (
        patch("orchestrator.coordinator.run_app_build") as mock_app_build,
        patch("orchestrator.coordinator.run_critic") as mock_critic,
    ):
        await _run_iteration_with(
            fake_mcp,
            **{"orchestrator.coordinator.run_iteration_agent": _fake_run_iteration_agent},
        )

    mock_app_build.assert_not_called()
    mock_critic.assert_not_called()
    final = fake_mcp.job_statuses[-1]
    assert final["status"] == "needs_clarification"
    assert final["error_detail"] == "Which scene did you mean?"
    assert "complete" not in [entry["status"] for entry in fake_mcp.job_statuses]


async def test_iteration_agent_raising_marks_failed_needs_review():
    fake_mcp = FakeMcp(script_text="")

    async def _raise(project_id, user_request, requested_by):
        raise RuntimeError("mcp_server unreachable")

    await _run_iteration_with(
        fake_mcp, **{"orchestrator.coordinator.run_iteration_agent": _raise}
    )

    final = fake_mcp.job_statuses[-1]
    assert final["status"] == "failed_needs_review"
    assert "mcp_server unreachable" in final["error_detail"]


async def test_iteration_critic_failure_still_follows_bounded_retry_policy():
    fake_mcp = FakeMcp(script_text="")
    critic_calls = 0

    async def _always_fail(project_id, *, scoped_shot_ids=None):
        nonlocal critic_calls
        critic_calls += 1
        return Verdict(passed=False, notes="still broken")

    await _run_iteration_with(
        fake_mcp, **{"orchestrator.coordinator.run_critic": _always_fail}
    )

    assert critic_calls == 2
    assert fake_mcp.job_statuses[-1]["status"] == "failed_needs_review"
