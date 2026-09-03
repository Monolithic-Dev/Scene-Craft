"""Entrypoint: run(project_id, user_request, requested_by) -> IterationResult.

Flow (PHASE-05-ITERATION-AND-TRACE-UI.md SS3):
1. get_project_state + get_edit_history (MCP) — current shots and recent
   edits, the latter being this agent's memory source for follow-up
   requests ("also revert the earlier lighting change").
2. Call Gemini with the diff-extraction prompt.
3. If clarification_needed is set (or extraction itself fails), stop —
   never apply a guessed change (Common Pitfall #1).
4. Otherwise validate each diff's field against EDITABLE_FIELDS (defense in
   depth beyond the prompt's own constraint — Common Pitfall #2) and apply
   the valid ones via write_shot_edit.
"""
import logging
from dataclasses import dataclass, field
from typing import Any

from iteration_agent.prompts import build_iteration_prompt
from iteration_agent.schema import IterationOutput
from shared.gemini_client import GeminiClientError, generate_json
from shared.mcp_client import get_edit_history, get_project_state, write_shot_edit

logger = logging.getLogger("scenecraft.iteration_agent")

EDITABLE_FIELDS = {"location", "time_of_day", "action_summary", "suggested_camera", "characters"}


@dataclass
class IterationResult:
    affected_shot_ids: list[str] = field(default_factory=list)
    clarification_needed: str | None = None
    invalid_fields_skipped: list[str] = field(default_factory=list)


def _shot_summaries(state: dict[str, Any]) -> list[dict[str, Any]]:
    summaries = []
    for scene in state.get("existing_scenes", []):
        for shot in scene.get("shots", []):
            summaries.append(
                {
                    "shot_id": shot["id"],
                    "scene": scene["heading"],
                    "action_summary": shot["action_summary"],
                    "location": shot["location"],
                    "time_of_day": shot["time_of_day"],
                    "suggested_camera": shot["suggested_camera"],
                    "characters": shot.get("characters", []),
                }
            )
    return summaries


async def run(project_id: str, user_request: str, requested_by: str) -> IterationResult:
    state = await get_project_state(project_id)
    history = await get_edit_history(project_id)
    shot_summaries = _shot_summaries(state)

    prompt = build_iteration_prompt(shot_summaries, history.get("edits", []), user_request)
    try:
        text = generate_json(prompt, IterationOutput)
        output = IterationOutput.model_validate_json(text)
    except (GeminiClientError, ValueError) as exc:
        # An extraction failure is treated the same as "ambiguous" — never
        # apply a guessed change just because the model call itself broke.
        logger.warning(
            "iteration_agent.extraction_failed", extra={"project_id": project_id, "error": str(exc)}
        )
        return IterationResult(clarification_needed=f"Couldn't interpret that request: {exc}")

    if output.clarification_needed:
        logger.info(
            "iteration_agent.clarification_needed",
            extra={"project_id": project_id, "question": output.clarification_needed},
        )
        return IterationResult(clarification_needed=output.clarification_needed)

    affected_shot_ids: list[str] = []
    invalid_fields_skipped: list[str] = []
    for diff in output.diffs:
        if diff.field not in EDITABLE_FIELDS:
            invalid_fields_skipped.append(diff.field)
            continue
        await write_shot_edit(diff.shot_id, diff.field, diff.new_value, requested_by)
        if diff.shot_id not in affected_shot_ids:
            affected_shot_ids.append(diff.shot_id)

    if not affected_shot_ids and invalid_fields_skipped:
        # Every diff the model proposed used an invalid field — not a
        # legitimate "nothing to change" outcome, so fail loud rather than
        # silently completing a job that changed nothing.
        raise ValueError(
            f"Model proposed only invalid fields: {', '.join(invalid_fields_skipped)}"
        )

    logger.info(
        "iteration_agent.applied_edits",
        extra={"project_id": project_id, "affected_shot_ids": affected_shot_ids},
    )
    return IterationResult(
        affected_shot_ids=affected_shot_ids, invalid_fields_skipped=invalid_fields_skipped
    )
