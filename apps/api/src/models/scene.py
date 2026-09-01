import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.script import Script
    from src.models.shot import Shot


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    script_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scripts.id"), index=True, nullable=False
    )
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(String(255), nullable=False)
    time_of_day: Mapped[str] = mapped_column(String(50), nullable=False, default="UNSPECIFIED")
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    script: Mapped["Script"] = relationship(back_populates="scenes")
    shots: Mapped[list["Shot"]] = relationship(
        back_populates="scene", cascade="all, delete-orphan", order_by="Shot.shot_number"
    )
