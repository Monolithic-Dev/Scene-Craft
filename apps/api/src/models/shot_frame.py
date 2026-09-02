import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.shot import Shot


class ShotFrame(Base):
    __tablename__ = "shot_frames"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # unique, not just indexed: one frame per shot in this version — a
    # regenerated frame overwrites in place (see ShotFrameRepository.upsert),
    # it never accumulates a history row per attempt.
    shot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shots.id"), unique=True, nullable=False
    )
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    alt_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    shot: Mapped["Shot"] = relationship(back_populates="frame")
