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

from src.api_client import ApiClientError, get_project_state, update_job_status, write_shot_records
from src.schemas import JobStatusUpdate, ProjectStateSnapshot, SceneInput, WriteResult

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
    job_id: str, status: str, error_detail: str | None = None
) -> JobStatusUpdate:
    """The channel agents use to move a GenerationJob through
    queued -> running -> complete|failed_needs_review — see
    PHASE-02-BREAKDOWN-AGENT.md agent.py flow step 6. Not one of the two
    tools originally scoped for Phase 2, added because agents have no other
    path to touch job state and the spec requires status updates at every
    stage transition.
    """
    try:
        return update_job_status(job_id, status, error_detail)
    except ApiClientError as exc:
        raise ValueError(str(exc)) from exc


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
