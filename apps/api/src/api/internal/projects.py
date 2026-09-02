from fastapi import APIRouter

from src.api.deps import DbSession
from src.api.internal.deps import RequireInternalService
from src.schemas.internal import (
    PrevisCustomizationWriteRequest,
    PrevisCustomizationWriteResponse,
    ProjectStateResponse,
)
from src.services.breakdown_service import BreakdownService
from src.services.previs_service import PrevisService

router = APIRouter(prefix="/projects", tags=["internal"])


@router.get("/{project_id}/state", response_model=ProjectStateResponse)
def get_project_state(
    project_id: str, db: DbSession, _: RequireInternalService
) -> ProjectStateResponse:
    return BreakdownService(db).get_project_state(project_id)


@router.post("/{project_id}/previs-customization", response_model=PrevisCustomizationWriteResponse)
def write_previs_customization(
    project_id: str,
    payload: PrevisCustomizationWriteRequest,
    db: DbSession,
    _: RequireInternalService,
) -> PrevisCustomizationWriteResponse:
    """Backs the write_previs_customization MCP tool — the App-Build Agent's
    one write per initial_generation job, per PHASE-04-APP-BUILD-AND-CRITIC.md
    SS3.
    """
    project = PrevisService(db).write_customization(
        project_id,
        title=payload.title,
        accent_color=payload.accent_color,
        tone_note=payload.tone_note,
    )
    customization = project.previs_customization or {}
    return PrevisCustomizationWriteResponse(
        project_id=project.id,
        title=customization["title"],
        accent_color=customization["accent_color"],
        tone_note=customization["tone_note"],
    )
