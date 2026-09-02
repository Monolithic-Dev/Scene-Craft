from sqlalchemy.orm import Session

from src.core.exceptions import NotFoundError
from src.models.project import Project
from src.repositories.project_repository import ProjectRepository


class PrevisService:
    """Backs the internal write_previs_customization tool — the App-Build
    Agent's only path to persist its one LLM-authored artifact, per
    PHASE-04-APP-BUILD-AND-CRITIC.md SS3. Mirrors FrameService's role for
    shot frames.
    """

    def __init__(self, db: Session) -> None:
        self._projects = ProjectRepository(db)

    def write_customization(
        self, project_id: str, *, title: str, accent_color: str, tone_note: str
    ) -> Project:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found")

        return self._projects.update_previs_customization(
            project, {"title": title, "accent_color": accent_color, "tone_note": tone_note}
        )
