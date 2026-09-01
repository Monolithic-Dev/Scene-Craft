from fastapi import APIRouter

from src.api.deps import DbSession
from src.api.internal.deps import RequireInternalService
from src.schemas.internal import (
    ProjectStateResponse,
    WriteBreakdownRequest,
    WriteBreakdownResponse,
)
from src.services.breakdown_service import BreakdownService

router = APIRouter(prefix="/projects", tags=["internal"])


@router.get("/{project_id}/state", response_model=ProjectStateResponse)
def get_project_state(
    project_id: str, db: DbSession, _: RequireInternalService
) -> ProjectStateResponse:
    return BreakdownService(db).get_project_state(project_id)


@router.post("/{project_id}/scripts/{script_id}/breakdown", response_model=WriteBreakdownResponse)
def write_breakdown(
    project_id: str,
    script_id: str,
    payload: WriteBreakdownRequest,
    db: DbSession,
    _: RequireInternalService,
) -> WriteBreakdownResponse:
    """project_id is part of the URL for a resource-scoped path; the write
    itself is scoped by script_id, which BreakdownService validates.
    """
    return BreakdownService(db).write_breakdown(script_id, payload.scenes)
