from fastapi import APIRouter, BackgroundTasks, status

from src.api.deps import CurrentUser, DbSession
from src.core.agent_runner import trigger_iteration_job
from src.models.generation_job import JobType
from src.schemas.project import IterateRequest, IterateResponse
from src.services.job_service import JobService
from src.services.project_service import ProjectService

router = APIRouter(prefix="/projects/{project_id}/iterate", tags=["iterate"])


@router.post("", response_model=IterateResponse, status_code=status.HTTP_202_ACCEPTED)
def iterate(
    project_id: str,
    payload: IterateRequest,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> IterateResponse:
    """PHASE-05-ITERATION-AND-TRACE-UI.md SS6 — creates an `iteration` job
    and hands the director's free-text request to the orchestrator, same
    fire-and-forget pattern as POST /projects/{id}/scripts.
    """
    ProjectService(db).get_owned_project(project_id, owner_id=current_user.id)

    job = JobService(db).create_job(project_id=project_id, job_type=JobType.ITERATION)
    background_tasks.add_task(
        trigger_iteration_job, job.id, project_id, payload.request, current_user.id
    )

    return IterateResponse(job_id=job.id)
