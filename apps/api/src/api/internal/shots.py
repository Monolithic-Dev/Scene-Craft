from fastapi import APIRouter

from src.api.deps import DbSession
from src.api.internal.deps import RequireInternalService
from src.schemas.internal import (
    ShotEditWriteRequest,
    ShotEditWriteResponse,
    ShotFrameWriteRequest,
    ShotFrameWriteResponse,
)
from src.services.frame_service import FrameService
from src.services.shot_edit_service import ShotEditService

router = APIRouter(prefix="/shots", tags=["internal"])


@router.post("/{shot_id}/frame", response_model=ShotFrameWriteResponse)
def write_frame(
    shot_id: str, payload: ShotFrameWriteRequest, db: DbSession, _: RequireInternalService
) -> ShotFrameWriteResponse:
    """Backs the write_frame_record MCP tool — PHASE-03-FRAME-GENERATION.md
    SS3 point 3. Each Frame Agent worker calls this once per shot.
    """
    frame = FrameService(db).write_frame(
        shot_id, payload.image_url, payload.alt_text, needs_review=payload.needs_review
    )
    return ShotFrameWriteResponse(shot_id=shot_id, frame_id=frame.id, updated_at=frame.generated_at)


@router.post("/{shot_id}/edit", response_model=ShotEditWriteResponse)
def write_shot_edit(
    shot_id: str, payload: ShotEditWriteRequest, db: DbSession, _: RequireInternalService
) -> ShotEditWriteResponse:
    """Backs the write_shot_edit MCP tool — the Iteration Agent's only path
    to apply a diff, per PHASE-05-ITERATION-AND-TRACE-UI.md SS3 point 4.
    Rejects any field outside EDITABLE_FIELDS (defense in depth beyond the
    prompt's own instruction — Common Pitfall #2).
    """
    edit = ShotEditService(db).apply_edit(
        shot_id, payload.field, payload.new_value, payload.requested_by
    )
    return ShotEditWriteResponse(
        shot_id=shot_id,
        edit_id=edit.id,
        field=edit.field,
        old_value=edit.old_value,
        new_value=edit.new_value,
        created_at=edit.created_at,
    )
