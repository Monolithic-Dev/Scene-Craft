from fastapi import APIRouter

from src.api.deps import DbSession
from src.api.internal.deps import RequireInternalService
from src.schemas.internal import WriteBreakdownRequest, WriteBreakdownResponse
from src.services.breakdown_service import BreakdownService

router = APIRouter(prefix="/scripts", tags=["internal"])


@router.post("/{script_id}/breakdown", response_model=WriteBreakdownResponse)
def write_breakdown(
    script_id: str, payload: WriteBreakdownRequest, db: DbSession, _: RequireInternalService
) -> WriteBreakdownResponse:
    """Matches write_shot_records(script_id, scenes) from
    PHASE-02-BREAKDOWN-AGENT.md SS2 exactly — no project_id, since
    BreakdownService resolves everything it needs from script_id alone.
    """
    return BreakdownService(db).write_breakdown(script_id, payload.scenes)
