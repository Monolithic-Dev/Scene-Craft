from datetime import datetime

from pydantic import BaseModel, Field

from src.schemas.scene import SceneResponse


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    style_reference: str | None = Field(default=None, max_length=2000)


class ProjectResponse(BaseModel):
    id: str
    title: str
    style_reference: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


class ProjectDetailResponse(ProjectResponse):
    """GET /projects/{id} only — includes the scene/shot breakdown once a
    generation job has completed (empty list before that, per
    PHASE-02-BREAKDOWN-AGENT.md SS5). Kept separate from ProjectResponse so
    the list/create endpoints stay light.
    """

    scenes: list[SceneResponse]
