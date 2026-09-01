from pydantic import BaseModel


class ShotResponse(BaseModel):
    id: str
    shot_number: int
    characters: list[str]
    location: str
    time_of_day: str
    action_summary: str
    suggested_camera: str
    dialogue_snippet: str | None

    model_config = {"from_attributes": True}


class SceneResponse(BaseModel):
    id: str
    scene_number: int
    heading: str
    time_of_day: str
    needs_review: bool
    shots: list[ShotResponse]

    model_config = {"from_attributes": True}
