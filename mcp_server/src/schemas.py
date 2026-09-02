"""Tool I/O contracts. Mirrors apps/api/src/schemas/internal.py by necessity
(a network boundary) — keep the two in sync by hand when the breakdown
output contract changes.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class ShotInput(BaseModel):
    shot_number: int
    characters: list[str] = Field(default_factory=list)
    location: str
    time_of_day: str = "UNSPECIFIED"
    action_summary: str
    suggested_camera: str
    dialogue_snippet: str | None = None


class FrameWriteResult(BaseModel):
    shot_id: str
    frame_id: str
    updated_at: datetime


class ExistingShotFrame(BaseModel):
    image_url: str
    alt_text: str


class SceneInput(BaseModel):
    scene_number: int
    heading: str
    time_of_day: str = "UNSPECIFIED"
    needs_review: bool = False
    shots: list[ShotInput] = Field(default_factory=list)


class WriteResult(BaseModel):
    scenes_written: int
    shots_written: int


class ExistingShot(BaseModel):
    id: str
    shot_number: int
    characters: list[str]
    location: str
    time_of_day: str
    action_summary: str
    suggested_camera: str
    dialogue_snippet: str | None
    needs_review: bool
    frame: ExistingShotFrame | None = None


class ExistingScene(BaseModel):
    scene_number: int
    heading: str
    time_of_day: str
    needs_review: bool
    shots: list[ExistingShot]


class PrevisCustomization(BaseModel):
    title: str
    accent_color: str
    tone_note: str


class ProjectStateSnapshot(BaseModel):
    project_id: str
    title: str
    script_id: str
    script_text: str
    style_reference: str | None
    existing_scenes: list[ExistingScene]
    previs_customization: PrevisCustomization | None = None


class JobStatusUpdate(BaseModel):
    job_id: str
    status: str
    updated_at: datetime


class PrevisCustomizationWriteResult(BaseModel):
    project_id: str
    title: str
    accent_color: str
    tone_note: str
