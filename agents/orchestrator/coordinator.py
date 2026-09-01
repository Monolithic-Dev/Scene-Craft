"""Entry point for every job. For initial_generation, Phase 2's plan is
just [breakdown] — later phases extend it to
[breakdown, frames, app_build, critic], per 04-AGENT-ARCHITECTURE.md SS1.

Invoked as: python -m orchestrator.coordinator <job_id> <project_id>
(spawned by apps/api/src/core/agent_runner.py — see that module's docstring
for why this is a subprocess and not an in-process call).
"""
import asyncio
import logging
import sys

from breakdown_agent.agent import run as run_breakdown
from shared.mcp_client import McpClientError, update_job_status

logger = logging.getLogger("scenecraft.orchestrator")
logging.basicConfig(level=logging.INFO)


async def run_initial_generation(job_id: str, project_id: str) -> None:
    try:
        await update_job_status(job_id, "running")
    except McpClientError:
        logger.exception("coordinator.failed_to_mark_running", extra={"job_id": job_id})
        return

    try:
        result = await run_breakdown(project_id)
    except Exception as exc:
        # Top-level job boundary: every failure here must become
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
            "scenes_processed": result.scenes_processed,
            "scenes_flagged": result.scenes_flagged,
        },
    )
    await update_job_status(job_id, "complete")


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python -m orchestrator.coordinator <job_id> <project_id>", file=sys.stderr)
        raise SystemExit(2)
    job_id, project_id = sys.argv[1], sys.argv[2]
    asyncio.run(run_initial_generation(job_id, project_id))


if __name__ == "__main__":
    main()
