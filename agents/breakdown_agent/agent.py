"""Entrypoint: run(project_id) -> BreakdownResult.

Flow (PHASE-02-BREAKDOWN-AGENT.md SS3):
1. get_project_state (MCP) for script text + any existing partial breakdown
   (resuming a failed job) — seeds known characters/locations.
2. Chunk the script on scene boundaries.
3. Per chunk: call Gemini, validate against BreakdownOutput.
4. On validation failure: re-prompt once with the error appended. On a
   second failure, flag that scene needs_review and continue — one bad
   scene must not fail the whole job.
5. write_shot_records (MCP) to persist each chunk's result as it completes,
   so a crash partway through still leaves earlier scenes durably written.
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from breakdown_agent.chunking import chunk_script
from breakdown_agent.prompts import build_breakdown_prompt, build_reprompt
from breakdown_agent.schema import BreakdownOutput, SceneOutput
from shared.gemini_client import GeminiClientError, generate_json
from shared.mcp_client import get_project_state, write_shot_records

logger = logging.getLogger("scenecraft.breakdown_agent")

_HEADING_LINE_RE = re.compile(r"^.*$", re.MULTILINE)


@dataclass
class BreakdownResult:
    scenes_processed: int
    scenes_flagged: int


def _fallback_heading(chunk_text: str) -> str:
    match = _HEADING_LINE_RE.match(chunk_text.strip())
    return match.group(0).strip() if match else "UNKNOWN HEADING"


def _known_entities(existing_scenes: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    characters: list[str] = []
    locations: list[str] = []
    for scene in existing_scenes:
        for shot in scene.get("shots", []):
            for character in shot.get("characters", []):
                if character not in characters:
                    characters.append(character)
            location = shot.get("location")
            if location and location not in locations:
                locations.append(location)
    return characters, locations


async def _generate_with_retry(
    prompt: str, chunk_index: int
) -> tuple[BreakdownOutput | None, str | None]:
    """Returns (parsed_output, None) on success, or (None, last_error) after
    exhausting one re-prompt attempt.
    """
    try:
        text = generate_json(prompt, BreakdownOutput)
        return BreakdownOutput.model_validate_json(text), None
    except (ValidationError, json.JSONDecodeError, GeminiClientError) as first_error:
        reprompt = build_reprompt(prompt, str(first_error))
        try:
            text2 = generate_json(reprompt, BreakdownOutput)
            return BreakdownOutput.model_validate_json(text2), None
        except (ValidationError, json.JSONDecodeError, GeminiClientError) as second_error:
            return None, str(second_error)


async def run(project_id: str) -> BreakdownResult:
    state = await get_project_state(project_id)
    script_id: str = state["script_id"]
    known_characters, known_locations = _known_entities(state.get("existing_scenes", []))

    chunks = chunk_script(state["script_text"])
    scenes_processed = 0
    scenes_flagged = 0
    # Authoritative, monotonically increasing across the whole script — each
    # chunk is processed with zero visibility into any other chunk, so
    # Gemini's own returned scene_number is meaningless as a global ordinal
    # (every chunk sees exactly one scene and will tend to call it "1").
    # Trusting it would collide every chunk onto the same upsert key.
    next_scene_number = 1

    for index, chunk in enumerate(chunks, start=1):
        prompt = build_breakdown_prompt(chunk, known_characters, known_locations)
        output, error = await _generate_with_retry(prompt, index)

        if output is None:
            logger.warning(
                "breakdown_agent.scene_flagged",
                extra={"script_id": script_id, "chunk_index": index, "error": error},
            )
            flagged_scene = SceneOutput(
                scene_number=next_scene_number,
                heading=_fallback_heading(chunk),
                time_of_day="UNSPECIFIED",
                shots=[],
            )
            await write_shot_records(
                script_id, [_scene_write_payload(flagged_scene, needs_review=True)]
            )
            next_scene_number += 1
            scenes_flagged += 1
            continue

        for scene in output.scenes:
            scene.scene_number = next_scene_number
            next_scene_number += 1
            await write_shot_records(script_id, [_scene_write_payload(scene, needs_review=False)])
            scenes_processed += 1
            for shot in scene.shots:
                for character in shot.characters:
                    if character not in known_characters:
                        known_characters.append(character)
                if shot.location not in known_locations:
                    known_locations.append(shot.location)

    return BreakdownResult(scenes_processed=scenes_processed, scenes_flagged=scenes_flagged)


def _scene_write_payload(scene: SceneOutput, *, needs_review: bool) -> dict[str, Any]:
    return {
        "scene_number": scene.scene_number,
        "heading": scene.heading,
        "time_of_day": scene.time_of_day,
        "needs_review": needs_review,
        "shots": [shot.model_dump() for shot in scene.shots],
    }
