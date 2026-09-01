"""Wire-contract schemas for the internal API mcp_server calls.

These mirror the shapes in mcp_server/src/schemas.py and agents/breakdown_agent/schema.py
by necessity (a network boundary) — keep the three in sync by hand when the
breakdown output contract changes.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class ShotWriteInput(BaseModel):
    shot_number: int
    characters: list[str] = Field(default_factory=list)
    location: str
    time_of_day: str = "UNSPECIFIED"
    action_summary: str
    suggested_camera: str
    dialogue_snippet: str | None = None


class SceneWriteInput(BaseModel):
    scene_number: int
    heading: str
    time_of_day: str = "UNSPECIFIED"
    needs_review: bool = False
    shots: list[ShotWriteInput] = Field(default_factory=list)


class WriteBreakdownRequest(BaseModel):
    scenes: list[SceneWriteInput]


class WriteBreakdownResponse(BaseModel):
    scenes_written: int
    shots_written: int


class ExistingShotState(BaseModel):
    shot_number: int
    characters: list[str]
    location: str
    time_of_day: str
    action_summary: str
    suggested_camera: str
    dialogue_snippet: str | None


class ExistingSceneState(BaseModel):
    scene_number: int
    heading: str
    time_of_day: str
    needs_review: bool
    shots: list[ExistingShotState]


class ProjectStateResponse(BaseModel):
    project_id: str
    script_id: str
    script_text: str
    style_reference: str | None
    existing_scenes: list[ExistingSceneState]


class JobStatusUpdateRequest(BaseModel):
    status: str
    error_detail: str | None = None


class JobStatusUpdateResponse(BaseModel):
    job_id: str
    status: str
    updated_at: datetime
