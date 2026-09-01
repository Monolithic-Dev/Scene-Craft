from sqlalchemy.orm import Session

from src.core.exceptions import NotFoundError
from src.repositories.project_repository import ProjectRepository
from src.repositories.scene_repository import SceneRepository
from src.repositories.script_repository import ScriptRepository
from src.schemas.internal import (
    ExistingSceneState,
    ExistingShotState,
    ProjectStateResponse,
    SceneWriteInput,
    WriteBreakdownResponse,
)


class BreakdownService:
    """Backs the internal API that mcp_server's tools wrap — see
    03-SYSTEM-DESIGN.md SS2 ("MCP Layer"). This is apps/api's own trusted
    boundary; mcp_server never touches these tables directly.
    """

    def __init__(self, db: Session) -> None:
        self._projects = ProjectRepository(db)
        self._scripts = ScriptRepository(db)
        self._scenes = SceneRepository(db)

    def get_project_state(self, project_id: str) -> ProjectStateResponse:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found")

        script = self._scripts.get_latest_for_project(project_id)
        if script is None:
            raise NotFoundError(f"Project '{project_id}' has no uploaded script")

        existing_scenes = [
            ExistingSceneState(
                scene_number=scene.scene_number,
                heading=scene.heading,
                time_of_day=scene.time_of_day,
                needs_review=scene.needs_review,
                shots=[
                    ExistingShotState(
                        shot_number=shot.shot_number,
                        characters=shot.characters,
                        location=shot.location,
                        time_of_day=shot.time_of_day,
                        action_summary=shot.action_summary,
                        suggested_camera=shot.suggested_camera,
                        dialogue_snippet=shot.dialogue_snippet,
                    )
                    for shot in scene.shots
                ],
            )
            for scene in self._scenes.list_for_script(script.id)
        ]

        return ProjectStateResponse(
            project_id=project.id,
            script_id=script.id,
            script_text=script.raw_text,
            style_reference=project.style_reference,
            existing_scenes=existing_scenes,
        )

    def write_breakdown(
        self, script_id: str, scenes: list[SceneWriteInput]
    ) -> WriteBreakdownResponse:
        script = self._scripts.get_by_id(script_id)
        if script is None:
            raise NotFoundError(f"Script '{script_id}' not found")

        shots_written = 0
        for scene_input in scenes:
            scene = self._scenes.upsert_scene(script_id, scene_input)
            shots_written += len(scene.shots)

        return WriteBreakdownResponse(scenes_written=len(scenes), shots_written=shots_written)
