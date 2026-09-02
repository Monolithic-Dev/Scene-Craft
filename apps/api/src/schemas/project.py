from datetime import datetime

from pydantic import BaseModel, Field

from src.schemas.scene import SceneResponse


class PrevisCustomizationResponse(BaseModel):
    title: str
    accent_color: str
    tone_note: str

    model_config = {"from_attributes": True}


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
    # Added in Phase 4 — both None until the App-Build/Critic stages
    # complete. deployed_app_url comes from the project's latest
    # GenerationJob (PHASE-04-APP-BUILD-AND-CRITIC.md SS2), not a column on
    # Project itself.
    deployed_app_url: str | None = None
    previs_customization: PrevisCustomizationResponse | None = None
