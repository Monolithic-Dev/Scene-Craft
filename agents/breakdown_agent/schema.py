"""The contract every prompt must produce and every validator must check.
Mirrors mcp_server/src/schemas.py's SceneInput/ShotInput field-for-field —
this is the agent's own copy since it's what Gemini's response_schema is
built from directly.
"""
from pydantic import BaseModel


class ShotOutput(BaseModel):
    shot_number: int
    characters: list[str]
    location: str
    time_of_day: str
    action_summary: str
    suggested_camera: str
    dialogue_snippet: str | None = None


class SceneOutput(BaseModel):
    scene_number: int
    heading: str
    time_of_day: str
    shots: list[ShotOutput]


class BreakdownOutput(BaseModel):
    scenes: list[SceneOutput]
