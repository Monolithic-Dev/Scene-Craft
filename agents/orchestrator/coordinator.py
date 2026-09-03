"""Entry point for every job. Two plans, per 04-AGENT-ARCHITECTURE.md SS1:
initial_generation is [breakdown, frames, app_build, critic] (Phase 4);
iteration is [iteration, app_build (scoped), critic (scoped)] (Phase 5).

Invoked as:
  python -m orchestrator.coordinator <job_id> <project_id>
  python -m orchestrator.coordinator --iterate <job_id> <project_id> <user_request> <requested_by>
(spawned by apps/api/src/core/agent_runner.py — see that module's docstring
for why this is a subprocess and not an in-process call).
"""
import asyncio
import logging
import sys

from app_build_agent.agent import AppBuildResult
from app_build_agent.agent import run as run_app_build
from breakdown_agent.agent import run as run_breakdown
from critic_agent.agent import run as run_critic
from frame_agent.agent import run as run_frames
from iteration_agent.agent import run as run_iteration_agent
from shared.mcp_client import McpClientError, update_job_status
from shared.telemetry import agent_span

logger = logging.getLogger("scenecraft.orchestrator")
logging.basicConfig(level=logging.INFO)


async def _report_frame_progress(job_id: str, completed: int, total: int, failed: int) -> None:
    try:
        await update_job_status(
            job_id,
            "running",
            stage="frames",
            frames_total=total,
            frames_completed=completed,
            frames_failed=failed,
        )
    except McpClientError:
        # Progress reporting is best-effort — a transient mcp_server hiccup
        # mid-fan-out must not abort frame generation itself; the final
        # definitive update after run_frames() returns (below) still lands.
        logger.warning("coordinator.progress_report_failed", extra={"job_id": job_id})


async def _run_app_build_and_critic(
    job_id: str, project_id: str, *, scoped_shot_ids: list[str] | None = None
) -> AppBuildResult | None:
    """Shared by both job plans' common [app_build, critic] tail — see
    PHASE-04-APP-BUILD-AND-CRITIC.md SS4/SS6 for the bounded-retry policy
    and PHASE-05-ITERATION-AND-TRACE-UI.md SS4 for scoped_shot_ids. Returns
    the App-Build result on success, or None after already marking the job
    failed_needs_review — callers just check for None and return.
    """
    try:
        await update_job_status(job_id, "running", stage="app_build")
        async with agent_span("app_build", project_id=project_id, job_id=job_id):
            app_build_result = await run_app_build(project_id, scoped_shot_ids=scoped_shot_ids)
    except Exception as exc:
        logger.exception("coordinator.app_build_failed", extra={"job_id": job_id})
        await update_job_status(job_id, "failed_needs_review", error_detail=str(exc))
        return None

    try:
        await update_job_status(
            job_id,
            "running",
            stage="critic",
            deployed_app_url=app_build_result.deployed_app_url,
        )
        async with agent_span("critic", project_id=project_id, job_id=job_id) as span:
            verdict = await run_critic(project_id, scoped_shot_ids=scoped_shot_ids)
            if not verdict.passed:
                span.set_attribute("status", "retry")
    except Exception as exc:
        logger.exception("coordinator.critic_failed", extra={"job_id": job_id})
        await update_job_status(job_id, "failed_needs_review", error_detail=str(exc))
        return None

    if not verdict.passed:
        # Exactly one bounded retry through app_build, per PHASE-04-APP-
        # BUILD-AND-CRITIC.md SS4 — never an unbounded loop between the two.
        logger.warning(
            "coordinator.critic_verdict_failed_retrying",
            extra={"job_id": job_id, "notes": verdict.notes},
        )
        try:
            async with agent_span(
                "app_build", project_id=project_id, job_id=job_id, attempt=2
            ):
                app_build_result = await run_app_build(
                    project_id, scoped_shot_ids=scoped_shot_ids
                )
            async with agent_span(
                "critic", project_id=project_id, job_id=job_id, attempt=2
            ) as span:
                verdict = await run_critic(project_id, scoped_shot_ids=scoped_shot_ids)
                if not verdict.passed:
                    span.set_attribute("status", "failure")
        except Exception as exc:
            logger.exception("coordinator.app_build_retry_failed", extra={"job_id": job_id})
            await update_job_status(job_id, "failed_needs_review", error_detail=str(exc))
            return None

        if not verdict.passed:
            logger.warning(
                "coordinator.critic_verdict_failed_after_retry",
                extra={"job_id": job_id, "notes": verdict.notes},
            )
            await update_job_status(job_id, "failed_needs_review", error_detail=verdict.notes)
            return None

    return app_build_result


async def run_initial_generation(job_id: str, project_id: str) -> None:
    try:
        await update_job_status(job_id, "running", stage="breakdown")
    except McpClientError:
        logger.exception("coordinator.failed_to_mark_running", extra={"job_id": job_id})
        return

    try:
        async with agent_span("breakdown", project_id=project_id, job_id=job_id):
            breakdown_result = await run_breakdown(project_id)
    except Exception as exc:
        # Top-level stage boundary: every failure here must become
        # FAILED_NEEDS_REVIEW, not an uncaught exception that leaves the
        # job stuck at RUNNING forever — see 04-AGENT-ARCHITECTURE.md SS7
        # point 2 ("fail loud to the Coordinator, never fail silent").
        logger.exception("coordinator.breakdown_failed", extra={"job_id": job_id})
        await update_job_status(job_id, "failed_needs_review", error_detail=str(exc))
        return

    logger.info(
        "coordinator.breakdown_complete",
        extra={
            "job_id": job_id,
            "scenes_processed": breakdown_result.scenes_processed,
            "scenes_flagged": breakdown_result.scenes_flagged,
        },
    )

    try:
        await update_job_status(job_id, "running", stage="frames")
        async with agent_span("frames", project_id=project_id, job_id=job_id):
            frame_result = await run_frames(
                project_id,
                on_progress=lambda completed, total, failed: _report_frame_progress(
                    job_id, completed, total, failed
                ),
            )
    except Exception as exc:
        logger.exception("coordinator.frame_generation_failed", extra={"job_id": job_id})
        await update_job_status(job_id, "failed_needs_review", error_detail=str(exc))
        return

    logger.info(
        "coordinator.frames_complete",
        extra={
            "job_id": job_id,
            "frames_total": frame_result.frames_total,
            "frames_completed": frame_result.frames_completed,
            "frames_failed": frame_result.frames_failed,
        },
    )
    # Definitive final tally, sent unconditionally — covers the zero-shot
    # edge case (an empty breakdown never fires on_progress at all) and
    # guarantees GET /jobs/{id} shows accurate final counts regardless of
    # whether the last per-shot progress call landed.
    try:
        await update_job_status(
            job_id,
            "running",
            stage="frames",
            frames_total=frame_result.frames_total,
            frames_completed=frame_result.frames_completed,
            frames_failed=frame_result.frames_failed,
        )
    except McpClientError:
        logger.warning("coordinator.final_progress_report_failed", extra={"job_id": job_id})

    app_build_result = await _run_app_build_and_critic(job_id, project_id)
    if app_build_result is None:
        return

    await update_job_status(
        job_id, "complete", deployed_app_url=app_build_result.deployed_app_url
    )


async def run_iteration(job_id: str, project_id: str, user_request: str, requested_by: str) -> None:
    try:
        await update_job_status(job_id, "running", stage="iteration")
    except McpClientError:
        logger.exception("coordinator.failed_to_mark_running", extra={"job_id": job_id})
        return

    try:
        async with agent_span("iteration", project_id=project_id, job_id=job_id):
            iteration_result = await run_iteration_agent(project_id, user_request, requested_by)
    except Exception as exc:
        logger.exception("coordinator.iteration_failed", extra={"job_id": job_id})
        await update_job_status(job_id, "failed_needs_review", error_detail=str(exc))
        return

    if iteration_result.clarification_needed:
        # An expected, recoverable stop — never apply a guessed change, per
        # PHASE-05-ITERATION-AND-TRACE-UI.md Common Pitfall #1.
        logger.info("coordinator.iteration_needs_clarification", extra={"job_id": job_id})
        await update_job_status(
            job_id, "needs_clarification", error_detail=iteration_result.clarification_needed
        )
        return

    logger.info(
        "coordinator.iteration_complete",
        extra={"job_id": job_id, "affected_shot_ids": iteration_result.affected_shot_ids},
    )

    app_build_result = await _run_app_build_and_critic(
        job_id, project_id, scoped_shot_ids=iteration_result.affected_shot_ids
    )
    if app_build_result is None:
        return

    await update_job_status(
        job_id, "complete", deployed_app_url=app_build_result.deployed_app_url
    )


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--iterate":
        if len(args) != 5:
            print(
                "usage: python -m orchestrator.coordinator --iterate <job_id> <project_id> "
                "<user_request> <requested_by>",
                file=sys.stderr,
            )
            raise SystemExit(2)
        _, job_id, project_id, user_request, requested_by = args
        asyncio.run(run_iteration(job_id, project_id, user_request, requested_by))
        return

    if len(args) != 2:
        print("usage: python -m orchestrator.coordinator <job_id> <project_id>", file=sys.stderr)
        raise SystemExit(2)
    job_id, project_id = args
    asyncio.run(run_initial_generation(job_id, project_id))


if __name__ == "__main__":
    main()
