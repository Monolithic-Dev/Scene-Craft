"""Entrypoint: run(project_id) -> AppBuildResult.

Flow (PHASE-04-APP-BUILD-AND-CRITIC.md SS3):
1. get_project_state (MCP) for the title/style_reference/scene+shot data
   the customization prompt needs.
2. spec_builder.summarize — deterministic, no LLM.
3. customization.generate_customization — the one bounded LLM call, with its
   own retry-once-then-default handling; never raises.
4. write_previs_customization (MCP) to persist it.
5. Return the previs page's own URL — there is no separate deploy step per
   project, since the previs page is SceneCraft's own route rendering live
   data, not a generated app pushed somewhere else.
"""
from dataclasses import dataclass

from app_build_agent.customization import generate_customization
from app_build_agent.spec_builder import summarize
from shared.mcp_client import get_project_state, write_previs_customization


@dataclass
class AppBuildResult:
    deployed_app_url: str
    used_fallback_customization: bool


async def run(project_id: str) -> AppBuildResult:
    state = await get_project_state(project_id)
    summary = summarize(state)
    customization = generate_customization(summary)

    await write_previs_customization(
        project_id,
        summary.title,
        customization.accent_color,
        customization.tone_note,
    )

    return AppBuildResult(
        deployed_app_url=f"/projects/{project_id}/previs",
        used_fallback_customization=customization.used_fallback,
    )
