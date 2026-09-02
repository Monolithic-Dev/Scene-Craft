"""Entry point for every job. For initial_generation, the plan is
[breakdown, frames, app_build, critic] as of Phase 4, per
04-AGENT-ARCHITECTURE.md SS1.

Invoked as: python -m orchestrator.coordinator <job_id> <project_id>
(spawned by apps/api/src/core/agent_runner.py — see that module's docstring
for why this is a subprocess and not an in-process call).
"""
import asyncio
import logging
import sys

from app_build_agent.agent import run as run_app_build
from breakdown_agent.agent import run as run_breakdown
from critic_agent.agent import run as run_critic
from frame_agent.agent import run as run_frames
from shared.mcp_client import McpClientError, update_job_status

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


async def run_initial_generation(job_id: str, project_id: str) -> None:
    try:
        await update_job_status(job_id, "running", stage="breakdown")
    except McpClientError:
        logger.exception("coordinator.failed_to_mark_running", extra={"job_id": job_id})
        return

    try:
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

    try:
        await update_job_status(job_id, "running", stage="app_build")
        app_build_result = await run_app_build(project_id)
    except Exception as exc:
        logger.exception("coordinator.app_build_failed", extra={"job_id": job_id})
        await update_job_status(job_id, "failed_needs_review", error_detail=str(exc))
        return

    try:
        await update_job_status(
            job_id,
            "running",
            stage="critic",
            deployed_app_url=app_build_result.deployed_app_url,
        )
        verdict = await run_critic(project_id)
    except Exception as exc:
        logger.exception("coordinator.critic_failed", extra={"job_id": job_id})
        await update_job_status(job_id, "failed_needs_review", error_detail=str(exc))
        return

    if not verdict.passed:
        # Exactly one bounded retry through app_build, per PHASE-04-APP-
        # BUILD-AND-CRITIC.md SS4 — never an unbounded loop between the two.
        logger.warning(
            "coordinator.critic_verdict_failed_retrying",
            extra={"job_id": job_id, "notes": verdict.notes},
        )
        try:
            app_build_result = await run_app_build(project_id)
            verdict = await run_critic(project_id)
        except Exception as exc:
            logger.exception("coordinator.app_build_retry_failed", extra={"job_id": job_id})
            await update_job_status(job_id, "failed_needs_review", error_detail=str(exc))
            return

        if not verdict.passed:
            logger.warning(
                "coordinator.critic_verdict_failed_after_retry",
                extra={"job_id": job_id, "notes": verdict.notes},
            )
            await update_job_status(job_id, "failed_needs_review", error_detail=verdict.notes)
            return

    await update_job_status(
        job_id, "complete", deployed_app_url=app_build_result.deployed_app_url
    )


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python -m orchestrator.coordinator <job_id> <project_id>", file=sys.stderr)
        raise SystemExit(2)
    job_id, project_id = sys.argv[1], sys.argv[2]
    asyncio.run(run_initial_generation(job_id, project_id))


if __name__ == "__main__":
    main()
