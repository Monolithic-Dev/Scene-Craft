from sqlalchemy.orm import Session

from src.core.exceptions import NotFoundError
from src.models.shot_frame import ShotFrame
from src.repositories.shot_frame_repository import ShotFrameRepository


class FrameService:
    """Backs the internal write_frame_record tool — the Frame Agent's only
    path to persist a generated frame, per PHASE-03-FRAME-GENERATION.md SS3
    point 3. Mirrors BreakdownService's role for scenes/shots.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._frames = ShotFrameRepository(db)

    def write_frame(
        self, shot_id: str, image_url: str, alt_text: str, *, needs_review: bool
    ) -> ShotFrame:
        shot = self._frames.get_shot(shot_id)
        if shot is None:
            raise NotFoundError(f"Shot '{shot_id}' not found")

        # needs_review lives on Shot (the human-facing flag), not ShotFrame —
        # see Shot.needs_review's docstring for why it's shared with the
        # Breakdown Agent's existing needs_review convention.
        shot.needs_review = needs_review
        self._db.commit()

        return self._frames.upsert(shot_id, image_url, alt_text)
