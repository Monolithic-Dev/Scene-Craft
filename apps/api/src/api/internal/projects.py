from fastapi import APIRouter

from src.api.deps import DbSession
from src.api.internal.deps import RequireInternalService
from src.schemas.internal import ProjectStateResponse
from src.services.breakdown_service import BreakdownService

router = APIRouter(prefix="/projects", tags=["internal"])


@router.get("/{project_id}/state", response_model=ProjectStateResponse)
def get_project_state(
    project_id: str, db: DbSession, _: RequireInternalService
) -> ProjectStateResponse:
    return BreakdownService(db).get_project_state(project_id)
