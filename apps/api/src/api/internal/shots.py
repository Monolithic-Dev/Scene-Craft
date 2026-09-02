from fastapi import APIRouter

from src.api.deps import DbSession
from src.api.internal.deps import RequireInternalService
from src.schemas.internal import ShotFrameWriteRequest, ShotFrameWriteResponse
from src.services.frame_service import FrameService

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
