"""Entrypoint: run(project_id) -> Verdict.

Flow (PHASE-04-APP-BUILD-AND-CRITIC.md SS4):
1. get_project_state (MCP) — the same snapshot the App-Build Agent read
   from, so there is nothing here that could have drifted independently.
2. comparator.check_shot_coverage / validate_customization — both pure,
   deterministic checks.
3. Return a Verdict. The Coordinator owns the retry-then-escalate policy
   (PHASE-04-APP-BUILD-AND-CRITIC.md SS4/SS6) — this module only reports.
"""
from dataclasses import dataclass, field

from critic_agent.comparator import check_shot_coverage, validate_customization
from shared.mcp_client import get_project_state


@dataclass
class Verdict:
    passed: bool
    missing_shots: list[str] = field(default_factory=list)
    schema_errors: list[str] = field(default_factory=list)
    notes: str = ""


async def run(project_id: str) -> Verdict:
    state = await get_project_state(project_id)
    missing_shots = check_shot_coverage(state)
    schema_errors = validate_customization(state.get("previs_customization"))

    if not missing_shots and not schema_errors:
        return Verdict(passed=True)

    notes_parts = []
    if missing_shots:
        notes_parts.append(
            f"{len(missing_shots)} shot(s) missing a frame entirely: {', '.join(missing_shots)}"
        )
    if schema_errors:
        notes_parts.append("previs customization invalid: " + "; ".join(schema_errors))

    return Verdict(
        passed=False,
        missing_shots=missing_shots,
        schema_errors=schema_errors,
        notes=" | ".join(notes_parts),
    )
