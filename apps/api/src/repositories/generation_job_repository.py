from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.models.generation_job import GenerationJob, JobStatus, JobType


class GenerationJobRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, project_id: str, job_type: JobType) -> GenerationJob:
        job = GenerationJob(project_id=project_id, job_type=job_type, status=JobStatus.QUEUED)
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        return job

    def get_by_id(self, job_id: str) -> GenerationJob | None:
        return self._db.get(GenerationJob, job_id)

    def update_status(
        self, job: GenerationJob, status: JobStatus, error_detail: str | None = None
    ) -> GenerationJob:
        job.status = status
        if error_detail is not None:
            job.error_detail = error_detail
        if status in (JobStatus.COMPLETE, JobStatus.FAILED_NEEDS_REVIEW):
            job.completed_at = datetime.now(UTC)
        self._db.commit()
        self._db.refresh(job)
        return job
