"""Exercises the real MCP protocol dispatch (mcp.call_tool) — not just the
underlying Python functions — so "rejects invalid payload" reflects what an
actual agent-as-MCP-client would experience, including Pydantic validation
FastMCP runs before the tool body ever executes.
"""
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from src.schemas import (
    FrameWriteResult,
    JobStatusUpdate,
    PrevisCustomizationWriteResult,
    ProjectStateSnapshot,
    RecentEdits,
    ShotEditSummary,
    ShotEditWriteResult,
    WriteResult,
)
from src.server import mcp

_SNAPSHOT = ProjectStateSnapshot(
    project_id="proj-1",
    title="Midnight Ferry",
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
    mock_update.assert_called_once_with(
        "job-1",
        "running",
        None,
        stage=None,
        frames_total=None,
        frames_completed=None,
        frames_failed=None,
        deployed_app_url=None,
    )
    assert response[1]["status"] == "running"


async def test_update_job_status_forwards_frame_progress():
    update = JobStatusUpdate(job_id="job-1", status="running", updated_at=datetime.now(UTC))
    with patch("src.server.update_job_status", return_value=update) as mock_update:
        await mcp.call_tool(
            "update_job_status",
            {
                "job_id": "job-1",
                "status": "running",
                "stage": "frames",
                "frames_total": 18,
                "frames_completed": 12,
                "frames_failed": 1,
            },
        )
    mock_update.assert_called_once_with(
        "job-1",
        "running",
        None,
        stage="frames",
        frames_total=18,
        frames_completed=12,
        frames_failed=1,
        deployed_app_url=None,
    )


async def test_write_frame_record_persists_a_valid_payload():
    result = FrameWriteResult(shot_id="shot-1", frame_id="frame-1", updated_at=datetime.now(UTC))
    with patch("src.server.write_frame_record", return_value=result) as mock_write:
        response = await mcp.call_tool(
            "write_frame_record",
            {"shot_id": "shot-1", "image_url": "file:///a.png", "alt_text": "Dana waits."},
        )
    mock_write.assert_called_once_with(
        "shot-1", "file:///a.png", "Dana waits.", needs_review=False
    )
    assert response[1]["shot_id"] == "shot-1"


async def test_write_frame_record_rejects_missing_alt_text():
    with patch("src.server.write_frame_record") as mock_write:
        with pytest.raises(ToolError):
            await mcp.call_tool(
                "write_frame_record", {"shot_id": "shot-1", "image_url": "file:///a.png"}
            )
    mock_write.assert_not_called()


async def test_api_client_errors_surface_as_tool_errors():
    from src.api_client import ApiClientError

    with patch("src.server.get_project_state", side_effect=ApiClientError("apps/api returned 404")):
        with pytest.raises(ToolError, match="404"):
            await mcp.call_tool("get_project_state", {"project_id": "does-not-exist"})


async def test_update_job_status_forwards_deployed_app_url():
    update = JobStatusUpdate(job_id="job-1", status="running", updated_at=datetime.now(UTC))
    with patch("src.server.update_job_status", return_value=update) as mock_update:
        await mcp.call_tool(
            "update_job_status",
            {
                "job_id": "job-1",
                "status": "running",
                "stage": "app_build",
                "deployed_app_url": "/projects/proj-1/previs",
            },
        )
    mock_update.assert_called_once_with(
        "job-1",
        "running",
        None,
        stage="app_build",
        frames_total=None,
        frames_completed=None,
        frames_failed=None,
        deployed_app_url="/projects/proj-1/previs",
    )


async def test_write_previs_customization_persists_a_valid_payload():
    result = PrevisCustomizationWriteResult(
        project_id="proj-1", title="Midnight Ferry", accent_color="#ff6a00", tone_note="Tense"
    )
    with patch("src.server.write_previs_customization", return_value=result) as mock_write:
        response = await mcp.call_tool(
            "write_previs_customization",
            {
                "project_id": "proj-1",
                "title": "Midnight Ferry",
                "accent_color": "#ff6a00",
                "tone_note": "Tense",
            },
        )
    mock_write.assert_called_once_with("proj-1", "Midnight Ferry", "#ff6a00", "Tense")
    assert response[1]["title"] == "Midnight Ferry"


async def test_write_previs_customization_rejects_missing_fields():
    with patch("src.server.write_previs_customization") as mock_write:
        with pytest.raises(ToolError):
            await mcp.call_tool("write_previs_customization", {"project_id": "proj-1"})
    mock_write.assert_not_called()


async def test_write_shot_edit_persists_a_valid_payload():
    result = ShotEditWriteResult(
        shot_id="shot-1",
        edit_id="edit-1",
        field="time_of_day",
        old_value="DAY",
        new_value="NIGHT",
        created_at=datetime.now(UTC),
    )
    with patch("src.server.write_shot_edit", return_value=result) as mock_write:
        response = await mcp.call_tool(
            "write_shot_edit",
            {
                "shot_id": "shot-1",
                "field": "time_of_day",
                "new_value": "NIGHT",
                "requested_by": "user-1",
            },
        )
    mock_write.assert_called_once_with("shot-1", "time_of_day", "NIGHT", "user-1")
    assert response[1]["new_value"] == "NIGHT"


async def test_write_shot_edit_rejects_missing_fields():
    with patch("src.server.write_shot_edit") as mock_write:
        with pytest.raises(ToolError):
            await mcp.call_tool("write_shot_edit", {"shot_id": "shot-1"})
    mock_write.assert_not_called()


async def test_write_shot_edit_errors_surface_as_tool_errors():
    from src.api_client import ApiClientError

    with patch(
        "src.server.write_shot_edit", side_effect=ApiClientError("apps/api returned 400: bad field")
    ):
        with pytest.raises(ToolError, match="bad field"):
            await mcp.call_tool(
                "write_shot_edit",
                {"shot_id": "shot-1", "field": "id", "new_value": "x", "requested_by": "user-1"},
            )


async def test_get_edit_history_returns_recent_edits():
    result = RecentEdits(
        edits=[
            ShotEditSummary(
                shot_id="shot-1",
                field="location",
                old_value="Deck",
                new_value="Bridge",
                created_at=datetime.now(UTC),
            )
        ]
    )
    with patch("src.server.get_edit_history", return_value=result) as mock_get:
        response = await mcp.call_tool("get_edit_history", {"project_id": "proj-1"})
    mock_get.assert_called_once_with("proj-1", limit=10)
    assert response[1]["edits"][0]["field"] == "location"


async def test_get_edit_history_forwards_custom_limit():
    result = RecentEdits(edits=[])
    with patch("src.server.get_edit_history", return_value=result) as mock_get:
        await mcp.call_tool("get_edit_history", {"project_id": "proj-1", "limit": 3})
    mock_get.assert_called_once_with("proj-1", limit=3)
