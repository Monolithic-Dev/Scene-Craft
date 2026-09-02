"""The one LLM-authored write in this agent — accent_color/tone_note only,
never structure or content (PHASE-04-APP-BUILD-AND-CRITIC.md SS1). Mirrors
breakdown_agent's validate-then-reprompt-once pattern; unlike a flagged
scene, a bad customization call is never worth failing the job over
(PHASE-04-APP-BUILD-AND-CRITIC.md SS3: "on persistent schema-validation
failure, falls back to defaults and proceeds — styling is cosmetic, never
worth failing a job over") — so this falls back to a fixed default instead
of raising after the retry is exhausted.
"""
import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError, field_validator

from app_build_agent.prompts import build_customization_prompt, build_reprompt
from app_build_agent.spec_builder import ProjectSummary
from shared.gemini_client import GeminiClientError, generate_json

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT_ACCENT_COLOR = "#ff6a00"
DEFAULT_TONE_NOTE = "Storyboard previs — visual tone reference pending."


class CustomizationOutput(BaseModel):
    accent_color: str = Field(max_length=7)
    tone_note: str = Field(max_length=140)

    @field_validator("accent_color")
    @classmethod
    def _validate_hex(cls, value: str) -> str:
        if not _HEX_COLOR_RE.match(value):
            raise ValueError("accent_color must be a #rrggbb hex string")
        return value


@dataclass
class CustomizationResult:
    accent_color: str
    tone_note: str
    used_fallback: bool


def _generate_with_retry(prompt: str) -> CustomizationOutput | None:
    try:
        text = generate_json(prompt, CustomizationOutput)
        return CustomizationOutput.model_validate_json(text)
    except (ValidationError, json.JSONDecodeError, GeminiClientError) as first_error:
        reprompt = build_reprompt(prompt, str(first_error))
        try:
            text2 = generate_json(reprompt, CustomizationOutput)
            return CustomizationOutput.model_validate_json(text2)
        except (ValidationError, json.JSONDecodeError, GeminiClientError):
            return None


def generate_customization(summary: ProjectSummary) -> CustomizationResult:
    prompt = build_customization_prompt(summary)
    output = _generate_with_retry(prompt)
    if output is None:
        return CustomizationResult(
            accent_color=DEFAULT_ACCENT_COLOR, tone_note=DEFAULT_TONE_NOTE, used_fallback=True
        )
    return CustomizationResult(
        accent_color=output.accent_color, tone_note=output.tone_note, used_fallback=False
    )
