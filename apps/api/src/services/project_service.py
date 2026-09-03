from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from src.models.project import Project
from src.models.scene import Scene
from src.models.script import Script
from src.repositories.generation_job_repository import GenerationJobRepository
from src.repositories.project_repository import ProjectRepository
from src.repositories.scene_repository import SceneRepository
from src.repositories.script_repository import ScriptRepository

settings = get_settings()

_ALLOWED_SOURCE_FORMATS = {"text", "pdf"}


class ProjectService:
    def __init__(self, db: Session) -> None:
        self._projects = ProjectRepository(db)
        self._scripts = ScriptRepository(db)
        self._scenes = SceneRepository(db)
        self._jobs = GenerationJobRepository(db)

    def create_project(self, owner_id: str, title: str, style_reference: str | None) -> Project:
        return self._projects.create(
            owner_id=owner_id, title=title, style_reference=style_reference
        )

    def list_projects(self, owner_id: str) -> list[Project]:
        return self._projects.list_for_owner(owner_id)

    def get_owned_project(self, project_id: str, owner_id: str) -> Project:
        # Always check existence before ownership — reversing this order either
        # leaks existence information or produces confusing error messages.
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found")
        if project.owner_id != owner_id:
            raise ForbiddenError("You do not have access to this project")
        return project

    def upload_script(
        self,
        project_id: str,
        owner_id: str,
        raw_text: str,
        source_format: str,
        original_filename: str | None,
        content_length: int,
    ) -> Script:
        self.get_owned_project(project_id, owner_id)

        if source_format not in _ALLOWED_SOURCE_FORMATS:
            raise ValidationError(f"Unsupported script format: '{source_format}'")

        if content_length > settings.max_script_upload_bytes:
            max_mb = settings.max_script_upload_bytes / (1024 * 1024)
            raise ValidationError(f"Script exceeds the {max_mb:.0f}MB upload limit")

        if not raw_text.strip():
            raise ValidationError("Script content is empty")

        return self._scripts.create(
            project_id=project_id,
            raw_text=raw_text,
            source_format=source_format,
            original_filename=original_filename,
        )

    def get_breakdown(self, project_id: str) -> list[Scene]:
        """Empty until a generation job completes — never an error state."""
        script = self._scripts.get_latest_for_project(project_id)
        if script is None:
            return []
        return self._scenes.list_for_script(script.id)

    def get_deployed_app_url(self, project_id: str) -> str | None:
        """None until some job's App-Build stage has ever completed — never
        an error state, same convention as get_breakdown. Reflects the most
        recent job that actually deployed, not just the most recent job
        overall (a later iteration job stuck on needs_clarification or an
        early failure must not make an already-live previs disappear).
        """
        job = self._jobs.get_latest_deployed_for_project(project_id)
        return job.deployed_app_url if job is not None else None
