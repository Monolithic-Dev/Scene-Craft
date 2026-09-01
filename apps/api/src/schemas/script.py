from datetime import datetime

from pydantic import BaseModel


class ScriptResponse(BaseModel):
    id: str
    project_id: str
    source_format: str
    original_filename: str | None
    uploaded_at: datetime
    # Set on upload from Phase 2 onward — the generation job a client should
    # poll via GET /api/v1/jobs/{job_id}. Not part of the Script model
    # itself (a script can outlive many jobs); populated by the route.
    job_id: str | None = None

    model_config = {"from_attributes": True}
