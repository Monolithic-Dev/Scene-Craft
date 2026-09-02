from fastapi import APIRouter

from src.api.deps import DbSession
from src.api.internal.deps import RequireInternalService
from src.schemas.internal import JobStatusUpdateRequest, JobStatusUpdateResponse
from src.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["internal"])


@router.patch("/{job_id}/status", response_model=JobStatusUpdateResponse)
def update_job_status(
    job_id: str, payload: JobStatusUpdateRequest, db: DbSession, _: RequireInternalService
) -> JobStatusUpdateResponse:
    job = JobService(db).update_status(
        job_id,
        payload.status,
        payload.error_detail,
        stage=payload.stage,
        frames_total=payload.frames_total,
        frames_completed=payload.frames_completed,
        frames_failed=payload.frames_failed,
    )
    return JobStatusUpdateResponse(
        job_id=job.id,
        status=job.status.value,
        updated_at=job.completed_at or job.created_at,
    )
