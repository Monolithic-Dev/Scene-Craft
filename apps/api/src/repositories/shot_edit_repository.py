from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.scene import Scene
from src.models.script import Script
from src.models.shot import Shot
from src.models.shot_edit import ShotEdit

# Only these Shot fields are editable via natural-language iteration —
# PHASE-05-ITERATION-AND-TRACE-UI.md SS3's prompt already constrains the
# LLM to this same list; this is the defense-in-depth boundary (Common
# Pitfall #2: "LLM outputs are not a substitute for a validation boundary;
# keep both").
EDITABLE_FIELDS = {"location", "time_of_day", "action_summary", "suggested_camera", "characters"}


class ShotEditRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_shot(self, shot_id: str) -> Shot | None:
        return self._db.get(Shot, shot_id)

    def apply_edit(self, shot: Shot, field: str, new_value: str, requested_by: str) -> ShotEdit:
        # `characters` is the one editable field that isn't a plain string
        # on Shot — the diff's new_value still arrives as a string (matching
        # ShotEdit.new_value's text column and the Iteration Agent's
        # ShotDiff schema), parsed into a list only at the point of
        # assignment.
        if field == "characters":
            old_value = ", ".join(shot.characters)
            shot.characters = [c.strip() for c in new_value.split(",") if c.strip()]
        else:
            old_value = getattr(shot, field)
            setattr(shot, field, new_value)

        edit = ShotEdit(
            shot_id=shot.id,
            field=field,
            old_value=old_value,
            new_value=new_value,
            requested_by=requested_by,
        )
        self._db.add(edit)
        self._db.commit()
        self._db.refresh(edit)
        return edit

    def list_recent_for_project(self, project_id: str, limit: int = 10) -> list[ShotEdit]:
        stmt = (
            select(ShotEdit)
            .join(Shot, ShotEdit.shot_id == Shot.id)
            .join(Scene, Shot.scene_id == Scene.id)
            .join(Script, Scene.script_id == Script.id)
            .where(Script.project_id == project_id)
            .order_by(ShotEdit.created_at.desc())
            .limit(limit)
        )
        return list(self._db.execute(stmt).scalars().all())
