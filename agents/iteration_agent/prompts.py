"""The diff-extraction prompt — PHASE-05-ITERATION-AND-TRACE-UI.md SS3."""
from typing import Any

_PROMPT_TEMPLATE = """\
You are interpreting a director's requested change to a previs project.

Current shots (id, scene, summary, key fields):
{shot_summaries}

Recent edit history for context:
{recent_edits}

Director's request: "{user_request}"

Identify which shot(s) this request applies to and which field(s) change.
Only use these field names: location, time_of_day, action_summary,
suggested_camera, characters.

If the request clearly maps to specific shots and fields, output a list
of diffs. If it's ambiguous (e.g. "make it darker" without saying which
scene, or a request that doesn't map to any editable field), output a
clarification_needed question instead of guessing. Never apply a change
you're not confident about.

Return JSON matching this schema exactly:
{{"diffs": [{{"shot_id": "...", "field": "...", "new_value": "..."}}], \
"clarification_needed": "... or null"}}
"""


def _format_shot_summaries(shots: list[dict[str, Any]]) -> str:
    if not shots:
        return "(no shots yet)"
    lines = []
    for shot in shots:
        lines.append(
            f"- {shot['shot_id']} | {shot['scene']} | {shot['action_summary']} | "
            f"location={shot['location']} | time_of_day={shot['time_of_day']} | "
            f"camera={shot['suggested_camera']} | characters={', '.join(shot['characters'])}"
        )
    return "\n".join(lines)


def _format_recent_edits(edits: list[dict[str, Any]]) -> str:
    if not edits:
        return "(no prior edits)"
    lines = [
        f"- shot {edit['shot_id']}: {edit['field']} changed from "
        f"'{edit['old_value']}' to '{edit['new_value']}'"
        for edit in edits
    ]
    return "\n".join(lines)


def build_iteration_prompt(
    shot_summaries: list[dict[str, Any]],
    recent_edits: list[dict[str, Any]],
    user_request: str,
) -> str:
    return _PROMPT_TEMPLATE.format(
        shot_summaries=_format_shot_summaries(shot_summaries),
        recent_edits=_format_recent_edits(recent_edits),
        user_request=user_request,
    )
