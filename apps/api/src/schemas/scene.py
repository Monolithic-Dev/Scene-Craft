from datetime import datetime

from pydantic import BaseModel


class ShotFrameResponse(BaseModel):
    id: str
    image_url: str
    alt_text: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class ShotResponse(BaseModel):
    id: str
    shot_number: int
    characters: list[str]
    location: str
    time_of_day: str
    action_summary: str
    suggested_camera: str
    dialogue_snippet: str | None
    needs_review: bool
    frame: ShotFrameResponse | None

    model_config = {"from_attributes": True}


class SceneResponse(BaseModel):
    id: str
    scene_number: int
    heading: str
    time_of_day: str
    needs_review: bool
    shots: list[ShotResponse]

    model_config = {"from_attributes": True}
