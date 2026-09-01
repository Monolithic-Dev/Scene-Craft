from datetime import datetime

from pydantic import BaseModel

from src.models.generation_job import GenerationJob, JobStatus

# Phase 2 has exactly one agent in the plan (breakdown), so "steps" is
# derived from the job's own status column rather than a separate
# step-tracking table. Phase 5 replaces this with real per-agent step
# events streamed through Firestore — see PHASE-05-ITERATION-AND-TRACE-UI.md.
_STEP_STATUS_BY_JOB_STATUS: dict[JobStatus, str] = {
    JobStatus.QUEUED: "queued",
    JobStatus.RUNNING: "running",
    JobStatus.COMPLETE: "complete",
    JobStatus.FAILED_NEEDS_REVIEW: "failed",
}


class JobStep(BaseModel):
    agent: str
    status: str
    at: datetime | None


class JobResponse(BaseModel):
    id: str
    status: str
    steps: list[JobStep]
    deployed_app_url: str | None
    error_detail: str | None

    @classmethod
    def from_job(cls, job: GenerationJob) -> "JobResponse":
        step_status = _STEP_STATUS_BY_JOB_STATUS[job.status]
        at = job.completed_at if job.status != JobStatus.QUEUED else None
        return cls(
            id=job.id,
            status=job.status.value,
            steps=[JobStep(agent="breakdown", status=step_status, at=at)],
            deployed_app_url=job.deployed_app_url,
            error_detail=job.error_detail,
        )
