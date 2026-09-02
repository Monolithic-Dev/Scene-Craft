"""The customization prompt — the App-Build Agent's one LLM-authored
surface. Deliberately narrow: it never asks for structure or content, only
bounded presentation values the previs page's fixed shell already knows how
to render (PHASE-04-APP-BUILD-AND-CRITIC.md SS1).
"""
from app_build_agent.spec_builder import ProjectSummary

_PROMPT_TEMPLATE = """\
You are choosing a small set of presentation values for a film previs \
web app. Do not invent story content — only choose values that make an \
existing, fixed page layout feel tailored to this project's tone.

Project title: {title}
Visual style reference: {style_reference}
Scene count: {scene_count}
Shot count: {shot_count}
Sample shot actions:
{sample_actions}

Return JSON matching this schema exactly:
{{"accent_color": "#rrggbb hex string", "tone_note": "one short sentence, \
under 140 characters, describing the project's tone for a film crew \
audience"}}
"""


def build_customization_prompt(summary: ProjectSummary) -> str:
    sample_actions = (
        "\n".join(f"- {action}" for action in summary.sample_action_summaries)
        if summary.sample_action_summaries
        else "(none yet)"
    )
    return _PROMPT_TEMPLATE.format(
        title=summary.title,
        style_reference=summary.style_reference or "(none specified)",
        scene_count=summary.scene_count,
        shot_count=summary.shot_count,
        sample_actions=sample_actions,
    )


def build_reprompt(original_prompt: str, error: str) -> str:
    return (
        f"{original_prompt}\n\nYour previous response was invalid: {error}\n"
        "Return only the corrected JSON object, matching the schema exactly."
    )
