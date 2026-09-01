from fastapi import APIRouter

from src.api.deps import CurrentUser, DbSession
from src.schemas.job import JobResponse
from src.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: DbSession, current_user: CurrentUser) -> JobResponse:
    job = JobService(db).get_owned_job(job_id, owner_id=current_user.id)
    return JobResponse.from_job(job)
