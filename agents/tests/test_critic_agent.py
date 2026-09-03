"""Covers PHASE-04-APP-BUILD-AND-CRITIC.md SS8's Critic Agent required tests
(the retry-then-escalate loop itself is covered in test_coordinator.py,
since that policy lives in the Coordinator, not this agent).
"""
from unittest.mock import patch

from critic_agent.agent import run
from critic_agent.comparator import check_shot_coverage, validate_customization
from tests.conftest import FakeMcp

_VALID_CUSTOMIZATION = {"accent_color": "#ff6a00", "tone_note": "Tense, nocturnal."}


def _shot_with_frame(shot_id: str) -> dict:
    return {
        "id": shot_id,
        "shot_number": 1,
        "characters": [],
        "location": "Ferry deck",
        "time_of_day": "NIGHT",
        "action_summary": "x",
        "suggested_camera": "wide",
        "dialogue_snippet": None,
        "needs_review": False,
        "frame": {"image_url": "file:///a.png", "alt_text": "x"},
    }


def _shot_without_frame(shot_id: str) -> dict:
    shot = _shot_with_frame(shot_id)
    shot["frame"] = None
    return shot


# --- comparator (pure) -------------------------------------------------------


def test_check_shot_coverage_passes_when_every_shot_has_a_frame():
    shots = [_shot_with_frame("shot-1"), _shot_with_frame("shot-2")]
    state = {"existing_scenes": [{"shots": shots}]}
    assert check_shot_coverage(state) == []


def test_check_shot_coverage_reports_missing_frames():
    shots = [_shot_with_frame("shot-1"), _shot_without_frame("shot-2")]
    state = {"existing_scenes": [{"shots": shots}]}
    assert check_shot_coverage(state) == ["shot-2"]


def test_check_shot_coverage_scoped_ignores_shots_outside_the_scope():
    """PHASE-05-ITERATION-AND-TRACE-UI.md SS4: an iteration only re-verifies
    the shots it actually touched — an unrelated shot missing a frame
    (pre-existing, unrelated to this edit) must not block it.
    """
    shots = [_shot_with_frame("shot-1"), _shot_without_frame("shot-2")]
    state = {"existing_scenes": [{"shots": shots}]}
    assert check_shot_coverage(state, scoped_shot_ids=["shot-1"]) == []


def test_check_shot_coverage_scoped_still_reports_missing_shots_in_scope():
    shots = [_shot_without_frame("shot-1"), _shot_without_frame("shot-2")]
    state = {"existing_scenes": [{"shots": shots}]}
    assert check_shot_coverage(state, scoped_shot_ids=["shot-1"]) == ["shot-1"]


def test_validate_customization_passes_on_well_formed_input():
    assert validate_customization(_VALID_CUSTOMIZATION) == []


def test_validate_customization_flags_missing_customization():
    assert validate_customization(None) == ["previs_customization is missing"]


def test_validate_customization_flags_bad_hex_color():
    errors = validate_customization({"accent_color": "orange", "tone_note": "x"})
    assert len(errors) == 1
    assert "accent_color" in errors[0]


def test_validate_customization_flags_empty_tone_note():
    errors = validate_customization({"accent_color": "#ff6a00", "tone_note": "  "})
    assert len(errors) == 1
    assert "tone_note" in errors[0]


# --- agent.py (mocked MCP) --------------------------------------------------


async def test_critic_passes_on_matching_content():
    fake_mcp = FakeMcp(
        script_text="",
        existing_scenes=[{"shots": [_shot_with_frame("shot-1")]}],
        previs_customization=_VALID_CUSTOMIZATION,
    )
    with patch("critic_agent.agent.get_project_state", fake_mcp.get_project_state):
        verdict = await run("proj-1")

    assert verdict.passed is True
    assert verdict.missing_shots == []
    assert verdict.schema_errors == []


async def test_critic_detects_missing_shot():
    fake_mcp = FakeMcp(
        script_text="",
        existing_scenes=[{"shots": [_shot_without_frame("shot-1")]}],
        previs_customization=_VALID_CUSTOMIZATION,
    )
    with patch("critic_agent.agent.get_project_state", fake_mcp.get_project_state):
        verdict = await run("proj-1")

    assert verdict.passed is False
    assert verdict.missing_shots == ["shot-1"]
    assert "shot-1" in verdict.notes


async def test_critic_detects_missing_customization():
    fake_mcp = FakeMcp(
        script_text="",
        existing_scenes=[{"shots": [_shot_with_frame("shot-1")]}],
        previs_customization=None,
    )
    with patch("critic_agent.agent.get_project_state", fake_mcp.get_project_state):
        verdict = await run("proj-1")

    assert verdict.passed is False
    assert verdict.schema_errors == ["previs_customization is missing"]


async def test_critic_scoped_run_ignores_unrelated_missing_frames():
    fake_mcp = FakeMcp(
        script_text="",
        existing_scenes=[
            {"shots": [_shot_with_frame("shot-1"), _shot_without_frame("shot-2")]}
        ],
        previs_customization=_VALID_CUSTOMIZATION,
    )
    with patch("critic_agent.agent.get_project_state", fake_mcp.get_project_state):
        verdict = await run("proj-1", scoped_shot_ids=["shot-1"])

    assert verdict.passed is True
