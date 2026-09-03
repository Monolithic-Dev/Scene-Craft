"""Entrypoint: run(project_id, *, scoped_shot_ids=None) -> AppBuildResult.

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

Scoped rebuilds (Phase 5, PHASE-05-ITERATION-AND-TRACE-UI.md SS4): when
scoped_shot_ids is given (an iteration job), this is the "incremental path"
the doc describes — but because Phase 4's design has no per-shot data file
to regenerate (the previs route always reads shots live from the
database), a content-only edit needs zero App-Build work at all: the
change is already visible on next page load. So the incremental path here
is "skip the customization call entirely" rather than "regenerate part of
it" — accent_color/tone_note are project-level and a single-shot content
edit has no reason to change them. This is what makes a scoped run
measurably faster than a full initial generation.
"""
from dataclasses import dataclass

from app_build_agent.customization import generate_customization
from app_build_agent.spec_builder import summarize
from shared.mcp_client import get_project_state, write_previs_customization


@dataclass
class AppBuildResult:
    deployed_app_url: str
    used_fallback_customization: bool
    skipped_customization: bool = False


async def run(project_id: str, *, scoped_shot_ids: list[str] | None = None) -> AppBuildResult:
    if scoped_shot_ids is not None:
        return AppBuildResult(
            deployed_app_url=f"/projects/{project_id}/previs",
            used_fallback_customization=False,
            skipped_customization=True,
        )

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
