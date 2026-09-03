from sqlalchemy.orm import Session

from src.core.exceptions import NotFoundError, ValidationError
from src.models.shot_edit import ShotEdit
from src.repositories.shot_edit_repository import EDITABLE_FIELDS, ShotEditRepository


class ShotEditService:
    """Backs the write_shot_edit and get_edit_history MCP tools — the
    Iteration Agent's only path to touch shot data and its memory source,
    per PHASE-05-ITERATION-AND-TRACE-UI.md SS3.
    """

    def __init__(self, db: Session) -> None:
        self._edits = ShotEditRepository(db)

    def apply_edit(
        self, shot_id: str, field: str, new_value: str, requested_by: str
    ) -> ShotEdit:
        if field not in EDITABLE_FIELDS:
            raise ValidationError(f"'{field}' is not an editable shot field")
        shot = self._edits.get_shot(shot_id)
        if shot is None:
            raise NotFoundError(f"Shot '{shot_id}' not found")
        return self._edits.apply_edit(shot, field, new_value, requested_by)

    def get_recent_edits(self, project_id: str, limit: int = 10) -> list[ShotEdit]:
        return self._edits.list_recent_for_project(project_id, limit=limit)
