import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.scene import Scene
    from src.models.shot_frame import ShotFrame


class Shot(Base):
    __tablename__ = "shots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenes.id"), index=True, nullable=False
    )
    shot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Denormalized display list, not queried by character in this version —
    # see 05-DATABASE-DESIGN.md SS5 for the documented tradeoff.
    characters: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    time_of_day: Mapped[str] = mapped_column(String(50), nullable=False, default="UNSPECIFIED")
    action_summary: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_camera: Mapped[str] = mapped_column(String(255), nullable=False)
    dialogue_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Added in Phase 3 — reuses the same "needs a human look" signal already
    # established by scenes.needs_review (05-DATABASE-DESIGN.md SS3), now set
    # by the Frame Agent when a shot's frame generation exhausts its retries
    # or its caption generation fails. See PHASE-03-FRAME-GENERATION.md SS5.
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    scene: Mapped["Scene"] = relationship(back_populates="shots")
    frame: Mapped["ShotFrame | None"] = relationship(
        back_populates="shot", uselist=False, cascade="all, delete-orphan"
    )
