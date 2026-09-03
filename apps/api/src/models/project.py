import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.generation_job import GenerationJob
    from src.models.script import Script
    from src.models.user import User


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    style_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Added in Phase 4 — the App-Build Agent's one LLM-authored surface
    # (title/accent_color/tone_note), schema-validated before it ever lands
    # here. Everything else the previs page renders (scenes/shots/frames)
    # comes live from their own tables, never duplicated into this column —
    # see PHASE-04-APP-BUILD-AND-CRITIC.md SS1 for why: a persisted copy of
    # already-durable data can only go stale, so only the one genuinely
    # generated artifact gets a column of its own.
    previs_customization: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    owner: Mapped["User"] = relationship(back_populates="projects")
    scripts: Mapped[list["Script"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
