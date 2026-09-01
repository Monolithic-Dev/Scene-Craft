from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.scene import Scene
from src.models.shot import Shot
from src.schemas.internal import SceneWriteInput


class SceneRepository:
    """Upserts by (script_id, scene_number) — resumable: re-processing the same
    chunk on a retried job overwrites that scene's shots rather than duplicating
    them, per PHASE-02-BREAKDOWN-AGENT.md agent.py flow step 1.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_script(self, script_id: str) -> list[Scene]:
        stmt = select(Scene).where(Scene.script_id == script_id).order_by(Scene.scene_number)
        return list(self._db.execute(stmt).scalars().all())

    def get_by_script_and_number(self, script_id: str, scene_number: int) -> Scene | None:
        stmt = select(Scene).where(
            Scene.script_id == script_id, Scene.scene_number == scene_number
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def upsert_scene(self, script_id: str, scene_input: SceneWriteInput) -> Scene:
        scene = self.get_by_script_and_number(script_id, scene_input.scene_number)
        if scene is None:
            scene = Scene(script_id=script_id, scene_number=scene_input.scene_number)
            self._db.add(scene)

        scene.heading = scene_input.heading
        scene.time_of_day = scene_input.time_of_day
        scene.needs_review = scene_input.needs_review
        scene.shots.clear()
        for shot_input in scene_input.shots:
            scene.shots.append(
                Shot(
                    shot_number=shot_input.shot_number,
                    characters=shot_input.characters,
                    location=shot_input.location,
                    time_of_day=shot_input.time_of_day,
                    action_summary=shot_input.action_summary,
                    suggested_camera=shot_input.suggested_camera,
                    dialogue_snippet=shot_input.dialogue_snippet,
                )
            )

        self._db.commit()
        self._db.refresh(scene)
        return scene
