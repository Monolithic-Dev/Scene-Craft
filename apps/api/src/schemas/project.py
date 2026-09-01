from datetime import datetime

from pydantic import BaseModel, Field


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
