from pydantic import BaseModel, Field


class ShotDiff(BaseModel):
    shot_id: str
    field: str  # validated against EDITABLE_FIELDS in agent.py — defense in depth
    new_value: str


class IterationOutput(BaseModel):
    diffs: list[ShotDiff] = Field(default_factory=list)
    # Set instead of diffs if the request is ambiguous — never both at once,
    # per PHASE-05-ITERATION-AND-TRACE-UI.md SS3 point 3: "Never apply a
    # change you're not confident about."
    clarification_needed: str | None = None
