"""Spawns mcp_server as a subprocess over stdio and exposes typed methods for
the three tools it publishes. This is the *only* channel any agent uses to
touch project state — see 04-AGENT-ARCHITECTURE.md SS7 point 4.

Each call opens a fresh subprocess + stdio handshake rather than reusing one
persistent session across a job — simple and correct, measurably slower
(observed: ~1-2s of session overhead per call in local end-to-end testing).
Fine for Phase 2's per-scene call volume; worth a persistent-session
Coordinator-owned client if a later phase's call volume makes it worth it.
"""
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from shared.config import get_settings


class McpClientError(Exception):
    """Raised when a tool call fails — a bad response from apps/api, a
    Pydantic validation error on the arguments, or a transport failure.
    """


class McpClientNotConfiguredError(McpClientError):
    """Raised when mcp_server_python_executable isn't set. Distinct from
    McpClientError so callers can tell "not set up yet" apart from "set up
    but broke" — see agents/README for the setup step.
    """


def _server_params() -> StdioServerParameters:
    settings = get_settings()
    if not settings.mcp_server_python_executable:
        raise McpClientNotConfiguredError(
            "mcp_server_python_executable is not set — see agents/.env.example"
        )
    return StdioServerParameters(
        command=settings.mcp_server_python_executable,
        args=["-m", "src.server"],
        cwd=settings.mcp_server_working_dir,
    )


@asynccontextmanager
async def _session() -> AsyncIterator[ClientSession]:
    params = _server_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with _session() as session:
        result = await session.call_tool(name, arguments)

    first_block = result.content[0] if result.content else None
    first_text = first_block.text if isinstance(first_block, TextContent) else None

    if result.isError:
        raise McpClientError(f"{name} failed: {first_text or 'unknown MCP error'}")

    if result.structuredContent is not None:
        structured: dict[str, Any] = result.structuredContent
        return structured
    if first_text is not None:
        parsed: dict[str, Any] = json.loads(first_text)
        return parsed
    raise McpClientError(f"{name} returned no content")


async def get_project_state(project_id: str) -> dict[str, Any]:
    return await _call_tool("get_project_state", {"project_id": project_id})


async def write_shot_records(script_id: str, scenes: list[dict[str, Any]]) -> dict[str, Any]:
    return await _call_tool("write_shot_records", {"script_id": script_id, "scenes": scenes})


async def update_job_status(
    job_id: str,
    status: str,
    error_detail: str | None = None,
    *,
    stage: str | None = None,
    frames_total: int | None = None,
    frames_completed: int | None = None,
    frames_failed: int | None = None,
    deployed_app_url: str | None = None,
) -> dict[str, Any]:
    return await _call_tool(
        "update_job_status",
        {
            "job_id": job_id,
            "status": status,
            "error_detail": error_detail,
            "stage": stage,
            "frames_total": frames_total,
            "frames_completed": frames_completed,
            "frames_failed": frames_failed,
            "deployed_app_url": deployed_app_url,
        },
    )


async def write_frame_record(
    shot_id: str, image_url: str, alt_text: str, *, needs_review: bool = False
) -> dict[str, Any]:
    return await _call_tool(
        "write_frame_record",
        {
            "shot_id": shot_id,
            "image_url": image_url,
            "alt_text": alt_text,
            "needs_review": needs_review,
        },
    )


async def write_previs_customization(
    project_id: str, title: str, accent_color: str, tone_note: str
) -> dict[str, Any]:
    return await _call_tool(
        "write_previs_customization",
        {
            "project_id": project_id,
            "title": title,
            "accent_color": accent_color,
            "tone_note": tone_note,
        },
    )
