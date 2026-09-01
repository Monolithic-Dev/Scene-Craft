"""The core correctness bar for Phase 2 — see PHASE-02-BREAKDOWN-AGENT.md SS6.
Gemini itself is mocked (generate_json); the MCP layer is the FakeMcp
fixture from conftest.py. What's under real test is agent.py's own logic:
prompt sequencing, retry-on-failure, scene numbering, and flag-and-continue.
"""
import json
from unittest.mock import patch

from breakdown_agent.agent import run
from shared.gemini_client import GeminiClientError
from tests.conftest import FakeMcp

_SAMPLE_1 = "INT. FERRY - NIGHT\n\nDANA stares out at the water."

_SAMPLE_2 = """\
INT. FERRY - NIGHT

DANA stares out at the water.

EXT. DOCK - MORNING

The ferry docks. RAMOS waits on the pier.
"""


def _breakdown_json(scene_number: int, heading: str, time_of_day: str = "NIGHT") -> str:
    return json.dumps(
        {
            "scenes": [
                {
                    "scene_number": scene_number,
                    "heading": heading,
                    "time_of_day": time_of_day,
                    "shots": [
                        {
                            "shot_number": 1,
                            "characters": ["DANA"],
                            "location": "Ferry deck",
                            "time_of_day": time_of_day,
                            "action_summary": "Dana stares at the water.",
                            "suggested_camera": "wide",
                            "dialogue_snippet": None,
                        }
                    ],
                }
            ]
        }
    )


def _patched(fake_mcp: FakeMcp, generate_side_effect):
    return (
        patch("breakdown_agent.agent.get_project_state", fake_mcp.get_project_state),
        patch("breakdown_agent.agent.write_shot_records", fake_mcp.write_shot_records),
        patch("breakdown_agent.agent.generate_json", side_effect=generate_side_effect),
    )


async def test_breakdown_extracts_shots_from_sample_script_1():
    fake_mcp = FakeMcp(script_text=_SAMPLE_1)
    responses = [_breakdown_json(1, "INT. FERRY - NIGHT")]
    p1, p2, p3 = _patched(fake_mcp, responses)
    with p1, p2, p3:
        result = await run("proj-1")

    assert result.scenes_processed == 1
    assert result.scenes_flagged == 0
    assert len(fake_mcp.written_scenes) == 1
    assert fake_mcp.written_scenes[0]["heading"] == "INT. FERRY - NIGHT"
    assert fake_mcp.written_scenes[0]["shots"][0]["characters"] == ["DANA"]


async def test_breakdown_extracts_shots_from_sample_script_2_exercises_chunking():
    fake_mcp = FakeMcp(script_text=_SAMPLE_2)
    responses = [
        _breakdown_json(99, "INT. FERRY - NIGHT", "NIGHT"),  # scene_number deliberately wrong
        _breakdown_json(99, "EXT. DOCK - MORNING", "MORNING"),
    ]
    p1, p2, p3 = _patched(fake_mcp, responses)
    with p1, p2, p3:
        result = await run("proj-1")

    assert result.scenes_processed == 2
    # Gemini's own scene_number is never trusted across chunks — the agent
    # assigns document-order numbers itself (see agent.py's next_scene_number).
    assert [s["scene_number"] for s in fake_mcp.written_scenes] == [1, 2]
    assert fake_mcp.written_scenes[1]["heading"] == "EXT. DOCK - MORNING"


async def test_breakdown_handles_missing_time_of_day():
    fake_mcp = FakeMcp(script_text=_SAMPLE_1)
    response = json.dumps(
        {
            "scenes": [
                {
                    "scene_number": 1,
                    "heading": "INT. FERRY - UNSPECIFIED",
                    "time_of_day": "UNSPECIFIED",
                    "shots": [
                        {
                            "shot_number": 1,
                            "characters": [],
                            "location": "Ferry deck",
                            "time_of_day": "UNSPECIFIED",
                            "action_summary": "Dana stares at the water.",
                            "suggested_camera": "wide",
                        }
                    ],
                }
            ]
        }
    )
    p1, p2, p3 = _patched(fake_mcp, [response])
    with p1, p2, p3:
        await run("proj-1")

    assert fake_mcp.written_scenes[0]["time_of_day"] == "UNSPECIFIED"
    assert fake_mcp.written_scenes[0]["shots"][0]["time_of_day"] == "UNSPECIFIED"


async def test_breakdown_reprompts_on_invalid_json_then_succeeds():
    fake_mcp = FakeMcp(script_text=_SAMPLE_1)
    responses = ["not valid json at all", _breakdown_json(1, "INT. FERRY - NIGHT")]
    p1, p2, p3 = _patched(fake_mcp, responses)
    with p1, p2, p3:
        result = await run("proj-1")

    assert result.scenes_processed == 1
    assert result.scenes_flagged == 0
    assert len(fake_mcp.written_scenes) == 1


async def test_breakdown_flags_scene_after_second_failure():
    fake_mcp = FakeMcp(script_text=_SAMPLE_1)
    responses = ["still not valid json", "also not valid json"]
    p1, p2, p3 = _patched(fake_mcp, responses)
    with p1, p2, p3:
        result = await run("proj-1")

    assert result.scenes_processed == 0
    assert result.scenes_flagged == 1
    assert len(fake_mcp.written_scenes) == 1
    assert fake_mcp.written_scenes[0]["needs_review"] is True
    # The job still completes with a partial result rather than failing
    # entirely — see agent.py's module docstring point 4.
    assert fake_mcp.written_scenes[0]["heading"] == "INT. FERRY - NIGHT"


async def test_gemini_client_error_also_triggers_the_retry_path():
    fake_mcp = FakeMcp(script_text=_SAMPLE_1)
    responses = [GeminiClientError("safety block"), _breakdown_json(1, "INT. FERRY - NIGHT")]
    p1, p2, p3 = _patched(fake_mcp, responses)
    with p1, p2, p3:
        result = await run("proj-1")

    assert result.scenes_processed == 1
    assert result.scenes_flagged == 0


async def test_resuming_seeds_known_characters_from_existing_scenes():
    """Uses existing_scenes from a prior partial run so a resumed job's
    prompt includes prior chunks' entities for naming consistency, per
    agent.py flow step 1.
    """
    fake_mcp = FakeMcp(
        script_text=_SAMPLE_1,
        existing_scenes=[
            {
                "shots": [
                    {"characters": ["RAMOS"], "location": "Pier"},
                ]
            }
        ],
    )
    captured_prompts: list[str] = []

    async def _fake_get_project_state(project_id: str) -> dict:
        return await fake_mcp.get_project_state(project_id)

    def _fake_generate_json(prompt, response_schema, **kwargs):
        captured_prompts.append(prompt)
        return _breakdown_json(1, "INT. FERRY - NIGHT")

    with (
        patch("breakdown_agent.agent.get_project_state", _fake_get_project_state),
        patch("breakdown_agent.agent.write_shot_records", fake_mcp.write_shot_records),
        patch("breakdown_agent.agent.generate_json", side_effect=_fake_generate_json),
    ):
        await run("proj-1")

    assert "RAMOS" in captured_prompts[0]
    assert "Pier" in captured_prompts[0]
