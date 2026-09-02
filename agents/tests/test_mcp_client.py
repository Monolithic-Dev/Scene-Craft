"""Unit tests for the content-parsing/error-surfacing logic in _call_tool.
The real stdio transport is exercised manually against a running mcp_server
(see mcp_server's own test suite for the protocol-level coverage) — these
tests isolate what mcp_client.py itself is responsible for.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from shared.mcp_client import (
    McpClientError,
    McpClientNotConfiguredError,
    get_project_state,
    update_job_status,
    write_frame_record,
)


def _fake_session(result: MagicMock):
    @asynccontextmanager
    async def _session():
        session = AsyncMock()
        session.call_tool.return_value = result
        yield session

    return _session


async def test_get_project_state_uses_structured_content_when_present():
    result = MagicMock(isError=False, structuredContent={"project_id": "p1"}, content=[])
    with patch("shared.mcp_client._session", _fake_session(result)):
        response = await get_project_state("p1")
    assert response == {"project_id": "p1"}


async def test_falls_back_to_parsing_text_content_when_no_structured_content():
    text_block = TextContent(type="text", text='{"job_id": "j1", "status": "running"}')
    result = MagicMock(isError=False, structuredContent=None, content=[text_block])
    with patch("shared.mcp_client._session", _fake_session(result)):
        response = await update_job_status("j1", "running")
    assert response == {"job_id": "j1", "status": "running"}


async def test_error_result_raises_mcpclienterror_with_server_message():
    text_block = TextContent(type="text", text="Error executing tool: boom")
    result = MagicMock(isError=True, structuredContent=None, content=[text_block])
    with patch("shared.mcp_client._session", _fake_session(result)):
        with pytest.raises(McpClientError, match="boom"):
            await get_project_state("p1")


async def test_not_configured_raises_before_attempting_to_spawn_anything():
    with patch("shared.mcp_client.get_settings") as mock_settings:
        mock_settings.return_value.mcp_server_python_executable = ""
        with pytest.raises(McpClientNotConfiguredError):
            await get_project_state("p1")


async def test_update_job_status_forwards_progress_kwargs_as_tool_arguments():
    text_block = TextContent(type="text", text='{"job_id": "j1", "status": "running"}')
    result = MagicMock(isError=False, structuredContent=None, content=[text_block])

    captured_args: dict = {}

    @asynccontextmanager
    async def _session():
        session = AsyncMock()

        async def _call_tool(name, arguments):
            captured_args.update(arguments)
            return result

        session.call_tool = _call_tool
        yield session

    with patch("shared.mcp_client._session", _session):
        await update_job_status(
            "j1", "running", stage="frames", frames_total=18, frames_completed=12, frames_failed=1
        )

    assert captured_args == {
        "job_id": "j1",
        "status": "running",
        "error_detail": None,
        "stage": "frames",
        "frames_total": 18,
        "frames_completed": 12,
        "frames_failed": 1,
    }


async def test_write_frame_record_sends_expected_tool_arguments():
    text_block = TextContent(
        type="text",
        text='{"shot_id": "s1", "frame_id": "f1", "updated_at": "2026-01-01T00:00:00Z"}',
    )
    result = MagicMock(isError=False, structuredContent=None, content=[text_block])

    with patch("shared.mcp_client._session", _fake_session(result)):
        response = await write_frame_record(
            "s1", "file:///a.png", "Dana waits.", needs_review=True
        )

    assert response == {"shot_id": "s1", "frame_id": "f1", "updated_at": "2026-01-01T00:00:00Z"}
