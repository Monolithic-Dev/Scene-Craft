"""Covers PHASE-05-ITERATION-AND-TRACE-UI.md SS8's Iteration Agent required
tests. Gemini is mocked (generate_json); the MCP layer is the FakeMcp
fixture from conftest.py.
"""
import json
from unittest.mock import patch

from iteration_agent.agent import run
from shared.gemini_client import GeminiClientError
from tests.conftest import FakeMcp


def _shot(shot_id: str, **overrides) -> dict:
    base = {
        "id": shot_id,
        "shot_number": 1,
        "characters": ["DANA"],
        "location": "Ferry deck",
        "time_of_day": "DAY",
        "action_summary": "Dana waits.",
        "suggested_camera": "wide",
        "dialogue_snippet": None,
        "needs_review": False,
        "frame": None,
    }
    base.update(overrides)
    return base


def _state(shots: list[dict]) -> dict:
    return {"title": "Midnight Ferry", "existing_scenes": _scenes(shots)}


def _scenes(shots: list[dict]) -> list[dict]:
    return [{"heading": "INT. FERRY - NIGHT", "shots": shots}]


def _patched(fake_mcp: FakeMcp, generate_return_value: str):
    return (
        patch("iteration_agent.agent.get_project_state", fake_mcp.get_project_state),
        patch("iteration_agent.agent.get_edit_history", fake_mcp.get_edit_history),
        patch("iteration_agent.agent.write_shot_edit", fake_mcp.write_shot_edit),
        patch("iteration_agent.agent.generate_json", return_value=generate_return_value),
    )


async def test_iteration_extracts_single_field_diff():
    fake_mcp = FakeMcp(script_text="", existing_scenes=_scenes([_shot("shot-1")]))
    response = json.dumps(
        {"diffs": [{"shot_id": "shot-1", "field": "time_of_day", "new_value": "NIGHT"}]}
    )
    p1, p2, p3, p4 = _patched(fake_mcp, response)
    with p1, p2, p3, p4:
        result = await run("proj-1", "make scene 4 night-time", "user-1")

    assert result.affected_shot_ids == ["shot-1"]
    assert result.clarification_needed is None
    assert fake_mcp.written_edits == [
        {
            "shot_id": "shot-1",
            "field": "time_of_day",
            "new_value": "NIGHT",
            "requested_by": "user-1",
        }
    ]


async def test_iteration_extracts_multi_shot_diff():
    fake_mcp = FakeMcp(
        script_text="", existing_scenes=_scenes([_shot("shot-1"), _shot("shot-2")])
    )
    response = json.dumps(
        {
            "diffs": [
                {"shot_id": "shot-1", "field": "time_of_day", "new_value": "NIGHT"},
                {"shot_id": "shot-2", "field": "time_of_day", "new_value": "NIGHT"},
            ]
        }
    )
    p1, p2, p3, p4 = _patched(fake_mcp, response)
    with p1, p2, p3, p4:
        result = await run("proj-1", "make scene 4 night-time", "user-1")

    assert set(result.affected_shot_ids) == {"shot-1", "shot-2"}
    assert len(fake_mcp.written_edits) == 2


async def test_iteration_requests_clarification_on_ambiguous_input():
    fake_mcp = FakeMcp(script_text="", existing_scenes=_scenes([_shot("shot-1")]))
    response = json.dumps({"diffs": [], "clarification_needed": "Which scene did you mean?"})
    p1, p2, p3, p4 = _patched(fake_mcp, response)
    with p1, p2, p3, p4:
        result = await run("proj-1", "make it darker", "user-1")

    assert result.clarification_needed == "Which scene did you mean?"
    assert result.affected_shot_ids == []
    assert fake_mcp.written_edits == []


async def test_iteration_rejects_invalid_field_name():
    """Even if the LLM hallucinates a field name outside the allowed list,
    the validation layer catches it before it reaches the database — tested
    independently of the prompt (Common Pitfall #2).
    """
    fake_mcp = FakeMcp(script_text="", existing_scenes=_scenes([_shot("shot-1")]))
    response = json.dumps(
        {"diffs": [{"shot_id": "shot-1", "field": "id", "new_value": "hacked"}]}
    )
    p1, p2, p3, p4 = _patched(fake_mcp, response)
    with p1, p2, p3, p4:
        try:
            await run("proj-1", "change the id", "user-1")
            raised = False
        except ValueError:
            raised = True

    assert raised is True
    assert fake_mcp.written_edits == []


async def test_iteration_skips_invalid_fields_but_applies_valid_ones():
    fake_mcp = FakeMcp(script_text="", existing_scenes=_scenes([_shot("shot-1")]))
    response = json.dumps(
        {
            "diffs": [
                {"shot_id": "shot-1", "field": "id", "new_value": "hacked"},
                {"shot_id": "shot-1", "field": "time_of_day", "new_value": "NIGHT"},
            ]
        }
    )
    p1, p2, p3, p4 = _patched(fake_mcp, response)
    with p1, p2, p3, p4:
        result = await run("proj-1", "mixed request", "user-1")

    assert result.affected_shot_ids == ["shot-1"]
    assert result.invalid_fields_skipped == ["id"]
    assert len(fake_mcp.written_edits) == 1


async def test_iteration_uses_recent_edit_history_for_context():
    fake_mcp = FakeMcp(
        script_text="",
        existing_scenes=_scenes([_shot("shot-1")]),
        edit_history=[
            {
                "shot_id": "shot-1",
                "field": "location",
                "old_value": "Deck",
                "new_value": "Bridge",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
    )
    response = json.dumps(
        {"diffs": [{"shot_id": "shot-1", "field": "time_of_day", "new_value": "NIGHT"}]}
    )
    seen_prompts = []

    def _capture_generate_json(prompt, schema, **kwargs):
        seen_prompts.append(prompt)
        return response

    p1, p2, p3, _ = _patched(fake_mcp, response)
    with (
        p1,
        p2,
        p3,
        patch("iteration_agent.agent.generate_json", side_effect=_capture_generate_json),
    ):
        await run("proj-1", "revert the location change", "user-1")

    assert any("Bridge" in prompt for prompt in seen_prompts)


async def test_iteration_treats_generation_failure_as_clarification_needed():
    fake_mcp = FakeMcp(script_text="", existing_scenes=_scenes([_shot("shot-1")]))
    with (
        patch("iteration_agent.agent.get_project_state", fake_mcp.get_project_state),
        patch("iteration_agent.agent.get_edit_history", fake_mcp.get_edit_history),
        patch("iteration_agent.agent.write_shot_edit", fake_mcp.write_shot_edit),
        patch("iteration_agent.agent.generate_json", side_effect=GeminiClientError("empty")),
    ):
        result = await run("proj-1", "make it night", "user-1")

    assert result.clarification_needed is not None
    assert fake_mcp.written_edits == []
