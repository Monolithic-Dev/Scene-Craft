from datetime import datetime

from pydantic import BaseModel

from src.models.generation_job import GenerationJob, JobStatus, JobType

# "steps" is derived from the job's own status/current_stage/frames_*
# columns rather than a separate step-tracking table — see build_steps
# below. Phase 5 reuses this exact derivation to populate the Firestore
# trace mirror (src/core/firestore_client.py via JobService), so the two
# can never drift out of shape with each other; Cloud SQL (this table)
# stays the authoritative source either way.
_TERMINAL_STEP_STATUS_BY_JOB_STATUS: dict[JobStatus, str] = {
    JobStatus.COMPLETE: "complete",
    JobStatus.FAILED_NEEDS_REVIEW: "failed",
    # Added in Phase 5 — the Iteration Agent's ambiguous-request short
    # circuit (PHASE-05-ITERATION-AND-TRACE-UI.md SS3 point 3). Distinct
    # from "failed": an expected, recoverable stop, not an error.
    JobStatus.NEEDS_CLARIFICATION: "needs_clarification",
}
_STAGE_ORDER_BY_JOB_TYPE: dict[JobType, tuple[str, ...]] = {
    JobType.INITIAL_GENERATION: ("breakdown", "frames", "app_build", "critic"),
    # Added in Phase 5 — PHASE-05-ITERATION-AND-TRACE-UI.md SS5: "The
    # Coordinator's plan for job_type == iteration is
    # [iteration, app_build (scoped), critic (scoped)]".
    JobType.ITERATION: ("iteration", "app_build", "critic"),
}


class JobStep(BaseModel):
    agent: str
    status: str
    at: datetime | None
    completed: int | None = None
    total: int | None = None
    failed: int | None = None


class JobResponse(BaseModel):
    id: str
    status: str
    steps: list[JobStep]
    deployed_app_url: str | None
    # Added-to meaning in Phase 5: holds either a failure explanation
    # (FAILED_NEEDS_REVIEW) or the Iteration Agent's clarification question
    # (NEEDS_CLARIFICATION) — the two are mutually exclusive by definition
    # (a job has exactly one status), so one nullable field covers both
    # rather than adding a second, always-empty-in-the-other-case column.
    error_detail: str | None

    @classmethod
    def from_job(cls, job: GenerationJob) -> "JobResponse":
        return cls(
            id=job.id,
            status=job.status.value,
            steps=build_steps(job),
            deployed_app_url=job.deployed_app_url,
            error_detail=job.error_detail,
        )


def build_steps(job: GenerationJob) -> list[JobStep]:
    stage_order = _STAGE_ORDER_BY_JOB_TYPE[job.job_type]
    if job.status == JobStatus.QUEUED:
        return [JobStep(agent=stage_order[0], status="queued", at=None)]

    terminal_status = _TERMINAL_STEP_STATUS_BY_JOB_STATUS.get(job.status)
    current_stage_index = (
        stage_order.index(job.current_stage) if job.current_stage in stage_order else 0
    )

    steps: list[JobStep] = []
    for index, stage in enumerate(stage_order):
        if terminal_status in ("failed", "needs_clarification"):
            # Stages strictly before current_stage already succeeded; the
            # stop happened in current_stage itself; nothing after it ever
            # started. Without this split, a later-stage stop would wrongly
            # relabel an earlier stage that already succeeded.
            if index < current_stage_index:
                status = "complete"
            elif index == current_stage_index:
                status = terminal_status
            else:
                status = "not_started"
        elif terminal_status == "complete":
            status = "complete" if index <= current_stage_index else "not_started"
        elif index < current_stage_index:
            status = "complete"
        elif index == current_stage_index:
            status = "running"
        else:
            status = "queued"

        step = JobStep(agent=stage, status=status, at=job.completed_at)
        if stage == "frames" and status not in ("queued", "not_started"):
            step.completed = job.frames_completed
            step.total = job.frames_total
            step.failed = job.frames_failed
        steps.append(step)

    return steps
