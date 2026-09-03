from fastapi import APIRouter, status

from src.api.deps import CurrentUser, DbSession
from src.schemas.project import (
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectResponse,
)
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


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: str, db: DbSession, current_user: CurrentUser) -> ProjectDetailResponse:
    service = ProjectService(db)
    project = service.get_owned_project(project_id, owner_id=current_user.id)
    scenes = service.get_breakdown(project_id)
    deployed_app_url = service.get_deployed_app_url(project_id)
    # model_validate on a dict so ProjectResponse's ORM fields and the
    # scenes list (validated per-item via SceneResponse's from_attributes)
    # combine into one response without a second, duplicate schema.
    return ProjectDetailResponse.model_validate(
        {
            "id": project.id,
            "title": project.title,
            "style_reference": project.style_reference,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "scenes": scenes,
            "deployed_app_url": deployed_app_url,
            "previs_customization": project.previs_customization,
        }
    )
