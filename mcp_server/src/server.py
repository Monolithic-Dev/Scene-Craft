"""SceneCraft's internal MCP server.

Per 03-SYSTEM-DESIGN.md SS2: agents talk to project state exclusively
through these tools, never by importing apps/api's repository layer or
holding a SQLAlchemy session of their own. This is both a security boundary
(agents can't run arbitrary queries) and the literal MCP-server deliverable
the hackathon rubric asks for.

Every tool function is a plain, directly-testable Python function — the
@mcp.tool() decorator only adds the MCP protocol framing on top; tests call
these functions straight, without spinning up a stdio transport.
"""
from mcp.server.fastmcp import FastMCP

from src.api_client import (
    ApiClientError,
    get_project_state,
    update_job_status,
    write_frame_record,
    write_previs_customization,
    write_shot_records,
)
from src.schemas import (
    FrameWriteResult,
    JobStatusUpdate,
    PrevisCustomizationWriteResult,
    ProjectStateSnapshot,
    SceneInput,
    WriteResult,
)

mcp = FastMCP(name="scenecraft-mcp-server")


@mcp.tool(name="get_project_state")
def get_project_state_tool(project_id: str) -> ProjectStateSnapshot:
    """Read-only: returns everything an agent needs (script text, existing
    scenes/shots, style reference) in one call, so agents never make ad hoc
    direct queries. Supports resuming a failed job via existing_scenes.
    """
    try:
        return get_project_state(project_id)
    except ApiClientError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool(name="write_shot_records")
def write_shot_records_tool(script_id: str, scenes: list[SceneInput]) -> WriteResult:
    """Persists the Breakdown Agent's structured output. Rejects (via Pydantic
    validation on `scenes`, before this function body even runs) anything
    that doesn't match SceneInput/ShotInput — never silently coerced.
    """
    try:
        return write_shot_records(script_id, scenes)
    except ApiClientError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool(name="update_job_status")
def update_job_status_tool(
    job_id: str,
    status: str,
    error_detail: str | None = None,
    stage: str | None = None,
    frames_total: int | None = None,
    frames_completed: int | None = None,
    frames_failed: int | None = None,
    deployed_app_url: str | None = None,
) -> JobStatusUpdate:
    """The channel agents use to move a GenerationJob through
    queued -> running -> complete|failed_needs_review — see
    PHASE-02-BREAKDOWN-AGENT.md agent.py flow step 6. Not one of the two
    tools originally scoped for Phase 2, added because agents have no other
    path to touch job state and the spec requires status updates at every
    stage transition.

    stage/frames_* (added in Phase 3) let the Frame Agent's fan-out report
    real sub-progress mid-stage — see PHASE-03-FRAME-GENERATION.md SS6.
    deployed_app_url (added in Phase 4) is set once by the App-Build Agent —
    see PHASE-04-APP-BUILD-AND-CRITIC.md SS3. Any argument left as None
    carries no change; it is not the same as 0/unset.
    """
    try:
        return update_job_status(
            job_id,
            status,
            error_detail,
            stage=stage,
            frames_total=frames_total,
            frames_completed=frames_completed,
            frames_failed=frames_failed,
            deployed_app_url=deployed_app_url,
        )
    except ApiClientError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool(name="write_frame_record")
def write_frame_record_tool(
    shot_id: str, image_url: str, alt_text: str, needs_review: bool = False
) -> FrameWriteResult:
    """Persists one Frame Agent worker's result — a generated frame or a
    placeholder on persistent failure. See PHASE-03-FRAME-GENERATION.md SS3
    point 3 and SS5 for the placeholder/needs_review contract.
    """
    try:
        return write_frame_record(shot_id, image_url, alt_text, needs_review=needs_review)
    except ApiClientError as exc:
        raise ValueError(str(exc)) from exc


@mcp.tool(name="write_previs_customization")
def write_previs_customization_tool(
    project_id: str, title: str, accent_color: str, tone_note: str
) -> PrevisCustomizationWriteResult:
    """Persists the App-Build Agent's one LLM-authored artifact — a small,
    schema-validated styling/copy layer, not app code or content data. See
    PHASE-04-APP-BUILD-AND-CRITIC.md SS3.
    """
    try:
        return write_previs_customization(project_id, title, accent_color, tone_note)
    except ApiClientError as exc:
        raise ValueError(str(exc)) from exc


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
