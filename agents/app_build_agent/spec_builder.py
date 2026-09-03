"""Deterministic translation layer: ProjectState -> a compact summary used
to build the customization prompt. No LLM involved here — this must never
drift or hallucinate, per PHASE-04-APP-BUILD-AND-CRITIC.md SS1/SS3. The
previs page itself reads scenes/shots/frames straight from the same
ProjectState via apps/api's public API, never through a copy this module
produces — there is nothing here to keep in sync with the database.
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class ProjectSummary:
    title: str
    style_reference: str | None
    scene_count: int
    shot_count: int
    sample_action_summaries: list[str]


_MAX_SAMPLE_ACTIONS = 5


def summarize(state: dict[str, Any]) -> ProjectSummary:
    scenes = state.get("existing_scenes", [])
    shots = [shot for scene in scenes for shot in scene.get("shots", [])]
    sample_actions = [
        shot["action_summary"] for shot in shots[:_MAX_SAMPLE_ACTIONS] if shot.get("action_summary")
    ]

    return ProjectSummary(
        title=state.get("title") or "Untitled Project",
        style_reference=state.get("style_reference"),
        scene_count=len(scenes),
        shot_count=len(shots),
        sample_action_summaries=sample_actions,
    )
