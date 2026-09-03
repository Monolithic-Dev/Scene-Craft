import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.shot import Shot
    from src.models.user import User


class ShotEdit(Base):
    """Both the audit trail and the Iteration Agent's memory source — see
    PHASE-05-ITERATION-AND-TRACE-UI.md SS1: "don't build a separate 'memory'
    store when this table already captures what's needed."
    """

    __tablename__ = "shot_edits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shots.id"), index=True, nullable=False
    )
    field: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    shot: Mapped["Shot"] = relationship()
    user: Mapped["User"] = relationship()
