from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.project import Project


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, owner_id: str, title: str, style_reference: str | None) -> Project:
        project = Project(owner_id=owner_id, title=title, style_reference=style_reference)
        self._db.add(project)
        self._db.commit()
        self._db.refresh(project)
        return project

    def get_by_id(self, project_id: str) -> Project | None:
        return self._db.get(Project, project_id)

    def list_for_owner(self, owner_id: str) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.owner_id == owner_id)
            .order_by(Project.created_at.desc())
        )
        return list(self._db.execute(stmt).scalars().all())

    def update_previs_customization(
        self, project: Project, customization: dict[str, str]
    ) -> Project:
        project.previs_customization = customization
        self._db.commit()
        self._db.refresh(project)
        return project
