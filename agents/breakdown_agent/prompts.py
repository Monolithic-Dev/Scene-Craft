"""Prompt templates, versioned. See PHASE-02-BREAKDOWN-AGENT.md SS3 — this is
the real instruction sent to Gemini, not a summary.
"""

_BREAKDOWN_PROMPT = """\
You are a script supervisor's assistant. You will be given a chunk of a
screenplay, plus a list of characters and locations already identified in
earlier chunks (for consistency — reuse these names exactly if the same
entity appears again).

Extract every distinct shot implied by scene headings and action lines.
A new scene heading (INT./EXT. ... - DAY/NIGHT) always starts a new scene.
Within a scene, infer shot boundaries from clear action/camera cues in the
action lines — do not invent shots that aren't implied by the text.

Output strict JSON matching the BreakdownOutput schema. Do not include
markdown formatting, commentary, or any text outside the JSON object.
Do not invent characters, locations, or dialogue not present in the text.
If a field is genuinely unknown (e.g. no explicit time-of-day given),
use "UNSPECIFIED" rather than guessing.

Known characters so far: {known_characters}
Known locations so far: {known_locations}

Script chunk:
{chunk_text}
"""

_REPROMPT_SUFFIX = """

Your previous output failed validation: {error}. Fix and resend valid JSON only.
"""


def build_breakdown_prompt(
    chunk_text: str, known_characters: list[str], known_locations: list[str]
) -> str:
    return _BREAKDOWN_PROMPT.format(
        known_characters=", ".join(known_characters) or "(none yet)",
        known_locations=", ".join(known_locations) or "(none yet)",
        chunk_text=chunk_text,
    )


def build_reprompt(original_prompt: str, error: str) -> str:
    return original_prompt + _REPROMPT_SUFFIX.format(error=error)
