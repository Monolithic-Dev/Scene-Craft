from sqlalchemy.orm import Session

from src.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from src.models.generation_job import GenerationJob, JobStatus, JobType
from src.repositories.generation_job_repository import GenerationJobRepository
from src.repositories.project_repository import ProjectRepository

_VALID_STATUSES = {s.value for s in JobStatus}


class JobService:
    def __init__(self, db: Session) -> None:
        self._jobs = GenerationJobRepository(db)
        self._projects = ProjectRepository(db)

    def create_job(self, project_id: str, job_type: JobType) -> GenerationJob:
        return self._jobs.create(project_id=project_id, job_type=job_type)

    def get_owned_job(self, job_id: str, owner_id: str) -> GenerationJob:
        job = self._jobs.get_by_id(job_id)
        if job is None:
            raise NotFoundError(f"Job '{job_id}' not found")
        project = self._projects.get_by_id(job.project_id)
        if project is None or project.owner_id != owner_id:
            raise ForbiddenError("You do not have access to this job")
        return job

    def update_status(
        self,
        job_id: str,
        status: str,
        error_detail: str | None,
        *,
        stage: str | None = None,
        frames_total: int | None = None,
        frames_completed: int | None = None,
        frames_failed: int | None = None,
    ) -> GenerationJob:
        job = self._jobs.get_by_id(job_id)
        if job is None:
            raise NotFoundError(f"Job '{job_id}' not found")
        if status not in _VALID_STATUSES:
            raise ValidationError(f"Unknown job status: '{status}'")
        return self._jobs.update_status(
            job,
            JobStatus(status),
            error_detail=error_detail,
            stage=stage,
            frames_total=frames_total,
            frames_completed=frames_completed,
            frames_failed=frames_failed,
        )
