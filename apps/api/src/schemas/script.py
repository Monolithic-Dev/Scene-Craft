from datetime import datetime

from pydantic import BaseModel


class ScriptResponse(BaseModel):
    id: str
    project_id: str
    source_format: str
    original_filename: str | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}
