from fastapi import APIRouter, status

from src.api.deps import CurrentUser, DbSession
from src.schemas.project import ProjectCreateRequest, ProjectListResponse, ProjectResponse
from src.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreateRequest, db: DbSession, current_user: CurrentUser
) -> ProjectResponse:
    project = ProjectService(db).create_project(
        owner_id=current_user.id,
        title=payload.title,
        style_reference=payload.style_reference,
    )
    return ProjectResponse.model_validate(project)


@router.get("", response_model=ProjectListResponse)
def list_projects(db: DbSession, current_user: CurrentUser) -> ProjectListResponse:
    projects = ProjectService(db).list_projects(owner_id=current_user.id)
    return ProjectListResponse(projects=[ProjectResponse.model_validate(p) for p in projects])


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: DbSession, current_user: CurrentUser) -> ProjectResponse:
    project = ProjectService(db).get_owned_project(project_id, owner_id=current_user.id)
    return ProjectResponse.model_validate(project)
