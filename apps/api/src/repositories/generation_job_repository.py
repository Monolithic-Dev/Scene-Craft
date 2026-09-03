from datetime import UTC, datetime

from sqlalchemy import select
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

    def get_latest_for_project(self, project_id: str) -> GenerationJob | None:
        stmt = (
            select(GenerationJob)
            .where(GenerationJob.project_id == project_id)
            .order_by(GenerationJob.created_at.desc())
        )
        return self._db.execute(stmt).scalars().first()

    def get_latest_deployed_for_project(self, project_id: str) -> GenerationJob | None:
        # Backs ProjectDetailResponse.deployed_app_url (PHASE-04-APP-BUILD-
        # AND-CRITIC.md SS2) — the URL lives on the job, not the project,
        # since a project can accumulate multiple jobs over its lifetime.
        # Deliberately NOT just "the latest job": once Phase 5 lets a later
        # job stop short of app_build (needs_clarification, or an early
        # failure), the *most recent* job's own deployed_app_url is None
        # even though an earlier job's deployment is still live — the UI
        # must not lose the previs link just because the newest job never
        # got that far.
        stmt = (
            select(GenerationJob)
            .where(
                GenerationJob.project_id == project_id,
                GenerationJob.deployed_app_url.is_not(None),
            )
            .order_by(GenerationJob.created_at.desc())
        )
        return self._db.execute(stmt).scalars().first()

    def update_status(
        self,
        job: GenerationJob,
        status: JobStatus,
        error_detail: str | None = None,
        *,
        stage: str | None = None,
        frames_total: int | None = None,
        frames_completed: int | None = None,
        frames_failed: int | None = None,
        deployed_app_url: str | None = None,
    ) -> GenerationJob:
        job.status = status
        if error_detail is not None:
            job.error_detail = error_detail
        # None means "no update sent", not "reset to zero/unset" — a
        # per-shot progress call only carries the fields it changed.
        if stage is not None:
            job.current_stage = stage
        if frames_total is not None:
            job.frames_total = frames_total
        if frames_completed is not None:
            job.frames_completed = frames_completed
        if frames_failed is not None:
            job.frames_failed = frames_failed
        if deployed_app_url is not None:
            job.deployed_app_url = deployed_app_url
        if status in (JobStatus.COMPLETE, JobStatus.FAILED_NEEDS_REVIEW):
            job.completed_at = datetime.now(UTC)
        self._db.commit()
        self._db.refresh(job)
        return job
