from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.shot import Shot
from src.models.shot_frame import ShotFrame


class ShotFrameRepository:
    """Upserts by shot_id — a regenerated frame (retry, or a future Phase 5
    restyle) overwrites the existing row rather than accumulating a history
    of attempts, matching the one-frame-per-shot invariant on the
    shot_frames.shot_id unique constraint.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_shot_id(self, shot_id: str) -> ShotFrame | None:
        stmt = select(ShotFrame).where(ShotFrame.shot_id == shot_id)
        return self._db.execute(stmt).scalar_one_or_none()

    def upsert(self, shot_id: str, image_url: str, alt_text: str) -> ShotFrame:
        frame = self.get_by_shot_id(shot_id)
        if frame is None:
            frame = ShotFrame(shot_id=shot_id)
            self._db.add(frame)

        frame.image_url = image_url
        frame.alt_text = alt_text
        frame.generated_at = datetime.now(UTC)

        self._db.commit()
        self._db.refresh(frame)
        return frame

    def get_shot(self, shot_id: str) -> Shot | None:
        return self._db.get(Shot, shot_id)
