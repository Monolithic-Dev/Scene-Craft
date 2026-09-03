"""Covers PHASE-04-APP-BUILD-AND-CRITIC.md SS8's App-Build Agent required
tests. Gemini is mocked (generate_json); the MCP layer is the FakeMcp
fixture from conftest.py.
"""
import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app_build_agent.agent import run
from app_build_agent.customization import (
    DEFAULT_ACCENT_COLOR,
    DEFAULT_TONE_NOTE,
    CustomizationOutput,
    generate_customization,
)
from app_build_agent.spec_builder import summarize
from shared.gemini_client import GeminiClientError
from tests.conftest import FakeMcp


def _shot(shot_id: str, action_summary: str = "Dana stares at the water.") -> dict:
    return {
        "id": shot_id,
        "shot_number": 1,
        "characters": ["DANA"],
        "location": "Ferry deck",
        "time_of_day": "NIGHT",
        "action_summary": action_summary,
        "suggested_camera": "wide",
        "dialogue_snippet": None,
        "needs_review": False,
        "frame": {"image_url": "file:///a.png", "alt_text": "Dana at the rail."},
    }


def _valid_customization_json() -> str:
    return json.dumps({"accent_color": "#ff6a00", "tone_note": "Tense, nocturnal."})


# --- spec_builder (pure, no external calls) ---------------------------------


def test_spec_builder_produces_a_deterministic_summary():
    state = {
        "title": "Midnight Ferry",
        "style_reference": "neo-noir",
        "existing_scenes": [{"shots": [_shot("shot-1"), _shot("shot-2")]}],
    }
    summary = summarize(state)
    assert summary.title == "Midnight Ferry"
    assert summary.style_reference == "neo-noir"
    assert summary.scene_count == 1
    assert summary.shot_count == 2
    assert summary.sample_action_summaries == [
        "Dana stares at the water.",
        "Dana stares at the water.",
    ]


def test_spec_builder_handles_missing_title_and_empty_project():
    summary = summarize({"existing_scenes": []})
    assert summary.title == "Untitled Project"
    assert summary.scene_count == 0
    assert summary.shot_count == 0
    assert summary.sample_action_summaries == []


# --- customization (mocked Gemini) ------------------------------------------


def test_customization_validates_against_schema():
    with patch(
        "app_build_agent.customization.generate_json", return_value=_valid_customization_json()
    ):
        result = generate_customization(summarize({"existing_scenes": []}))

    assert result.accent_color == "#ff6a00"
    assert result.tone_note == "Tense, nocturnal."
    assert result.used_fallback is False


def test_customization_rejects_non_hex_accent_color():
    with pytest.raises(ValidationError):
        CustomizationOutput(accent_color="orange", tone_note="x")


def test_customization_retries_once_then_falls_back_to_defaults():
    with patch(
        "app_build_agent.customization.generate_json",
        side_effect=[GeminiClientError("empty response"), "not json"],
    ):
        result = generate_customization(summarize({"existing_scenes": []}))

    assert result.accent_color == DEFAULT_ACCENT_COLOR
    assert result.tone_note == DEFAULT_TONE_NOTE
    assert result.used_fallback is True


def test_customization_succeeds_on_the_reprompt():
    with patch(
        "app_build_agent.customization.generate_json",
        side_effect=[GeminiClientError("empty response"), _valid_customization_json()],
    ):
        result = generate_customization(summarize({"existing_scenes": []}))

    assert result.used_fallback is False
    assert result.accent_color == "#ff6a00"


# --- agent.py end-to-end (mocked Gemini + MCP) ------------------------------


def _patched(fake_mcp: FakeMcp, generate_return_value: str):
    return (
        patch("app_build_agent.agent.get_project_state", fake_mcp.get_project_state),
        patch(
            "app_build_agent.agent.write_previs_customization",
            fake_mcp.write_previs_customization,
        ),
        patch("app_build_agent.customization.generate_json", return_value=generate_return_value),
    )


async def test_app_build_writes_customization_and_returns_previs_url():
    fake_mcp = FakeMcp(
        script_text="",
        title="Midnight Ferry",
        existing_scenes=[{"shots": [_shot("shot-1")]}],
    )
    p1, p2, p3 = _patched(fake_mcp, _valid_customization_json())
    with p1, p2, p3:
        result = await run("proj-1")

    assert result.deployed_app_url == "/projects/proj-1/previs"
    assert result.used_fallback_customization is False
    assert fake_mcp.written_customizations == [
        {
            "project_id": "proj-1",
            "title": "Midnight Ferry",
            "accent_color": "#ff6a00",
            "tone_note": "Tense, nocturnal.",
        }
    ]


async def test_app_build_never_raises_on_customization_failure_alone():
    """Styling is cosmetic — a persistent Gemini failure falls back to
    defaults and still writes+returns successfully, per PHASE-04-APP-BUILD-
    AND-CRITIC.md SS3.
    """
    fake_mcp = FakeMcp(script_text="", existing_scenes=[{"shots": [_shot("shot-1")]}])
    with (
        patch("app_build_agent.agent.get_project_state", fake_mcp.get_project_state),
        patch(
            "app_build_agent.agent.write_previs_customization",
            fake_mcp.write_previs_customization,
        ),
        patch("app_build_agent.customization.generate_json", side_effect=GeminiClientError("x")),
    ):
        result = await run("proj-1")

    assert result.used_fallback_customization is True
    assert fake_mcp.written_customizations[0]["accent_color"] == DEFAULT_ACCENT_COLOR


# --- scoped/incremental rebuilds (Phase 5) ----------------------------------


async def test_app_build_scoped_run_skips_customization_entirely():
    """PHASE-05-ITERATION-AND-TRACE-UI.md SS4: because there is no per-shot
    data file to regenerate, a scoped (iteration) run needs zero App-Build
    work — no Gemini call, no write — which is what makes it measurably
    faster than a full initial generation.
    """
    fake_mcp = FakeMcp(script_text="", existing_scenes=[{"shots": [_shot("shot-1")]}])
    with (
        patch("app_build_agent.agent.get_project_state") as mock_state,
        patch(
            "app_build_agent.agent.write_previs_customization",
            fake_mcp.write_previs_customization,
        ),
        patch("app_build_agent.customization.generate_json") as mock_generate,
    ):
        result = await run("proj-1", scoped_shot_ids=["shot-1"])

    assert result.deployed_app_url == "/projects/proj-1/previs"
    assert result.skipped_customization is True
    mock_state.assert_not_called()
    mock_generate.assert_not_called()
    assert fake_mcp.written_customizations == []
