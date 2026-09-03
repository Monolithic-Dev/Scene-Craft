from fastapi import APIRouter

from src.api.deps import DbSession
from src.api.internal.deps import RequireInternalService
from src.schemas.internal import (
    PrevisCustomizationWriteRequest,
    PrevisCustomizationWriteResponse,
    ProjectStateResponse,
    RecentEditsResponse,
    ShotEditSummary,
)
from src.services.breakdown_service import BreakdownService
from src.services.previs_service import PrevisService
from src.services.shot_edit_service import ShotEditService

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


@router.get("/{project_id}/edit-history", response_model=RecentEditsResponse)
def get_edit_history(
    project_id: str, db: DbSession, _: RequireInternalService, limit: int = 10
) -> RecentEditsResponse:
    """Backs the get_edit_history MCP tool — the Iteration Agent's memory
    source, per PHASE-05-ITERATION-AND-TRACE-UI.md SS3 point 1 ("also revert
    the earlier lighting change" resolves via this history).
    """
    edits = ShotEditService(db).get_recent_edits(project_id, limit=limit)
    return RecentEditsResponse(
        edits=[
            ShotEditSummary(
                shot_id=edit.shot_id,
                field=edit.field,
                old_value=edit.old_value,
                new_value=edit.new_value,
                created_at=edit.created_at,
            )
            for edit in edits
        ]
    )
