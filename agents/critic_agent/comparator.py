"""Structural comparison against the same ProjectState snapshot everything
else in this pipeline reads from — no separate "expected" artifact to keep
in sync, per PHASE-04-APP-BUILD-AND-CRITIC.md SS4.
"""
import re
from typing import Any

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def check_shot_coverage(state: dict[str, Any]) -> list[str]:
    """Shot ids with no ShotFrame record at all — not the placeholder path
    (Phase 3 always writes a placeholder on persistent Imagen failure, which
    is a legitimate, already-flagged outcome), only a genuine gap where no
    frame was ever written for a shot.
    """
    missing: list[str] = []
    for scene in state.get("existing_scenes", []):
        for shot in scene.get("shots", []):
            if shot.get("frame") is None:
                missing.append(shot["id"])
    return missing


def validate_customization(customization: dict[str, Any] | None) -> list[str]:
    """Independent re-check of the App-Build Agent's one write — schema
    validation already happened at write time (agents/app_build_agent/
    customization.py), but the Critic Agent re-verifies rather than trusting
    that nothing went wrong between write and read.
    """
    if customization is None:
        return ["previs_customization is missing"]

    errors = []
    accent_color = customization.get("accent_color")
    if not isinstance(accent_color, str) or not _HEX_COLOR_RE.match(accent_color):
        errors.append("accent_color is missing or not a valid #rrggbb hex color")

    tone_note = customization.get("tone_note")
    if not isinstance(tone_note, str) or not tone_note.strip():
        errors.append("tone_note is missing or empty")

    return errors
