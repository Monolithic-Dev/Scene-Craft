import io

from fastapi import APIRouter, BackgroundTasks, File, UploadFile, status
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from src.api.deps import CurrentUser, DbSession
from src.core.agent_runner import trigger_breakdown_job
from src.core.exceptions import ValidationError
from src.models.generation_job import JobType
from src.schemas.script import ScriptResponse
from src.services.job_service import JobService
from src.services.project_service import ProjectService

router = APIRouter(prefix="/projects/{project_id}/scripts", tags=["scripts"])

_PDF_CONTENT_TYPES = {"application/pdf"}


def _extract_text(
    raw_bytes: bytes, content_type: str | None, filename: str | None
) -> tuple[str, str]:
    """Returns (extracted_text, source_format). Raises ValidationError on unsupported input."""
    is_pdf = content_type in _PDF_CONTENT_TYPES or (filename or "").lower().endswith(".pdf")
    if is_pdf:
        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
        except PdfReadError as exc:
            raise ValidationError("Could not read the uploaded PDF — file may be corrupt") from exc
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text, "pdf"

    try:
        return raw_bytes.decode("utf-8"), "text"
    except UnicodeDecodeError as exc:
        raise ValidationError("Unsupported file encoding — expected UTF-8 text or PDF") from exc


@router.post("", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def upload_script(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),  # noqa: B008 — FastAPI's required pattern for file uploads
) -> ScriptResponse:
    raw_bytes = await file.read()
    text, source_format = _extract_text(raw_bytes, file.content_type, file.filename)

    script = ProjectService(db).upload_script(
        project_id=project_id,
        owner_id=current_user.id,
        raw_text=text,
        source_format=source_format,
        original_filename=file.filename,
        content_length=len(raw_bytes),
    )

    job = JobService(db).create_job(project_id=project_id, job_type=JobType.INITIAL_GENERATION)
    background_tasks.add_task(trigger_breakdown_job, job.id)

    response = ScriptResponse.model_validate(script)
    response.job_id = job.id
    return response
