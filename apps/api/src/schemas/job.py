from datetime import datetime

from pydantic import BaseModel

from src.models.generation_job import GenerationJob, JobStatus

# The initial_generation plan is [breakdown, frames, app_build, critic] as of
# Phase 4 (04-AGENT-ARCHITECTURE.md SS1). "steps" is derived from the job's
# own status/current_stage/frames_* columns rather than a separate
# step-tracking table; Phase 5 replaces this with real per-agent step events
# streamed through Firestore — see PHASE-05-ITERATION-AND-TRACE-UI.md.
_TERMINAL_STEP_STATUS_BY_JOB_STATUS: dict[JobStatus, str] = {
    JobStatus.COMPLETE: "complete",
    JobStatus.FAILED_NEEDS_REVIEW: "failed",
}
_STAGE_ORDER = ("breakdown", "frames", "app_build", "critic")


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
    error_detail: str | None

    @classmethod
    def from_job(cls, job: GenerationJob) -> "JobResponse":
        return cls(
            id=job.id,
            status=job.status.value,
            steps=_build_steps(job),
            deployed_app_url=job.deployed_app_url,
            error_detail=job.error_detail,
        )


def _build_steps(job: GenerationJob) -> list[JobStep]:
    if job.status == JobStatus.QUEUED:
        return [JobStep(agent="breakdown", status="queued", at=None)]

    terminal_status = _TERMINAL_STEP_STATUS_BY_JOB_STATUS.get(job.status)
    current_stage_index = (
        _STAGE_ORDER.index(job.current_stage)
        if job.current_stage in _STAGE_ORDER
        else 0
    )

    steps: list[JobStep] = []
    for index, stage in enumerate(_STAGE_ORDER):
        if terminal_status == "failed":
            # Stages strictly before current_stage already succeeded; the
            # failure happened in current_stage itself; nothing after it
            # ever started. Without this split, a frames-stage failure would
            # wrongly relabel a breakdown stage that already succeeded.
            if index < current_stage_index:
                status = "complete"
            elif index == current_stage_index:
                status = "failed"
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
        if stage == "frames" and status != "queued" and status != "not_started":
            step.completed = job.frames_completed
            step.total = job.frames_total
            step.failed = job.frames_failed
        steps.append(step)

    return steps
