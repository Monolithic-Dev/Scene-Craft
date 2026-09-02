"""Imagen prompt template — exact text from PHASE-03-FRAME-GENERATION.md SS3.
The caption prompt lives in captioning.py, not here, since it's a distinct
concern (alt-text generation, not frame generation) with its own file in the
documented frame_agent/ layout (07-FOLDER-STRUCTURE.md).
"""

_FRAME_PROMPT_TEMPLATE = """\
Generate a storyboard-style concept frame for the following shot.

Shot action: {action_summary}
Camera: {suggested_camera}
Location: {location}
Time of day: {time_of_day}
Characters present: {characters}

Visual style (apply consistently): {project_style_reference}

Composition should read clearly as a single storyboard panel — favor
clarity of action and camera framing over photorealistic detail.\
"""

# The project style reference is nullable at project creation
# (05-DATABASE-DESIGN.md SS3) — PHASE-03-FRAME-GENERATION.md SS2 requires
# every prompt in a project to interpolate the exact same style string, so a
# missing one still needs *some* fixed fallback rather than an empty/None
# leaking into the prompt and drifting per shot.
DEFAULT_STYLE_REFERENCE = "clean black-and-white storyboard line art, minimal shading"


def build_frame_prompt(
    *,
    action_summary: str,
    suggested_camera: str,
    location: str,
    time_of_day: str,
    characters: list[str],
    style_reference: str | None,
) -> str:
    return _FRAME_PROMPT_TEMPLATE.format(
        action_summary=action_summary,
        suggested_camera=suggested_camera,
        location=location,
        time_of_day=time_of_day,
        characters=", ".join(characters) if characters else "none",
        project_style_reference=style_reference or DEFAULT_STYLE_REFERENCE,
    )
