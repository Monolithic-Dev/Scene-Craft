import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.project import Project


class JobType(enum.StrEnum):
    INITIAL_GENERATION = "initial_generation"
    ITERATION = "iteration"


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED_NEEDS_REVIEW = "failed_needs_review"
    # Added in Phase 5 — the Iteration Agent's short-circuit when a request
    # is ambiguous (PHASE-05-ITERATION-AND-TRACE-UI.md SS3 point 3: "do not
    # apply a guessed change"). Distinct from FAILED_NEEDS_REVIEW: this is
    # an expected, recoverable stop waiting on the user's next message, not
    # a failure.
    NEEDS_CLARIFICATION = "needs_clarification"


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        # Composite index for the "current job status" dashboard query hit on
        # every page load, per 05-DATABASE-DESIGN.md SS4.
        Index("ix_generation_jobs_project_id_status", "project_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    job_type: Mapped[JobType] = mapped_column(Enum(JobType), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), nullable=False, default=JobStatus.QUEUED
    )
    deployed_app_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Added in Phase 3 so GET /jobs/{id} can report real sub-progress during
    # frame generation (PHASE-03-FRAME-GENERATION.md SS6) instead of the
    # single synthetic status->step mapping Phase 2 used, which had no way to
    # represent "12 of 18 shots done". current_stage tracks which stage of
    # the plan is active ("breakdown" | "frames"); the frames_* counters are
    # only meaningful once current_stage == "frames".
    current_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frames_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frames_completed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frames_failed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="generation_jobs")
