"""Exercises the real MCP protocol dispatch (mcp.call_tool) — not just the
underlying Python functions — so "rejects invalid payload" reflects what an
actual agent-as-MCP-client would experience, including Pydantic validation
FastMCP runs before the tool body ever executes.
"""
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from src.schemas import JobStatusUpdate, ProjectStateSnapshot, WriteResult
from src.server import mcp

_SNAPSHOT = ProjectStateSnapshot(
    project_id="proj-1",
    script_id="script-1",
    script_text="INT. FERRY - NIGHT\n\nDana waits.",
    style_reference="neo-noir",
    existing_scenes=[],
)


async def test_get_project_state_returns_expected_shape():
    with patch("src.server.get_project_state", return_value=_SNAPSHOT) as mock_get:
        result = await mcp.call_tool("get_project_state", {"project_id": "proj-1"})
    mock_get.assert_called_once_with("proj-1")
    assert result[1] == _SNAPSHOT.model_dump(mode="json")


async def test_write_shot_records_rejects_invalid_payload():
    # Missing required fields (location, action_summary, suggested_camera)
    # on the shot — must fail before write_shot_records() is ever called.
    invalid_scenes = [{"scene_number": 1, "heading": "X", "shots": [{"shot_number": 1}]}]
    with patch("src.server.write_shot_records") as mock_write:
        with pytest.raises(ToolError):
            await mcp.call_tool(
                "write_shot_records", {"script_id": "script-1", "scenes": invalid_scenes}
            )
    mock_write.assert_not_called()


async def test_write_shot_records_persists_a_valid_payload():
    valid_scenes = [
        {
            "scene_number": 1,
            "heading": "INT. FERRY - NIGHT",
            "shots": [
                {
                    "shot_number": 1,
                    "location": "Ferry deck",
                    "action_summary": "Dana waits.",
                    "suggested_camera": "wide",
                }
            ],
        }
    ]
    result = WriteResult(scenes_written=1, shots_written=1)
    with patch("src.server.write_shot_records", return_value=result) as mock_write:
        response = await mcp.call_tool(
            "write_shot_records", {"script_id": "script-1", "scenes": valid_scenes}
        )
    assert mock_write.call_count == 1
    assert response[1] == result.model_dump(mode="json")


async def test_update_job_status_success():
    update = JobStatusUpdate(job_id="job-1", status="running", updated_at=datetime.now(UTC))
    with patch("src.server.update_job_status", return_value=update) as mock_update:
        response = await mcp.call_tool(
            "update_job_status", {"job_id": "job-1", "status": "running"}
        )
    mock_update.assert_called_once_with("job-1", "running", None)
    assert response[1]["status"] == "running"


async def test_api_client_errors_surface_as_tool_errors():
    from src.api_client import ApiClientError

    with patch("src.server.get_project_state", side_effect=ApiClientError("apps/api returned 404")):
        with pytest.raises(ToolError, match="404"):
            await mcp.call_tool("get_project_state", {"project_id": "does-not-exist"})
