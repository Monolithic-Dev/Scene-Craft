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


class ExistingShotFrameState(BaseModel):
    image_url: str
    alt_text: str


class ExistingShotState(BaseModel):
    # Added in Phase 3 — the Frame Agent fans out one worker per shot and
    # must write its ShotFrame record against the shot's real id (shots are
    # only ever addressed by scene_number+shot_number in the *write* path,
    # since SceneRepository.upsert_scene always fully replaces a scene's
    # shots — see PHASE-03-FRAME-GENERATION.md SS3).
    id: str
    shot_number: int
    characters: list[str]
    location: str
    time_of_day: str
    action_summary: str
    suggested_camera: str
    dialogue_snippet: str | None
    needs_review: bool
    # Added in Phase 4 — the App-Build/Critic Agents need frame coverage per
    # shot (PHASE-04-APP-BUILD-AND-CRITIC.md SS4); None until Phase 3's Frame
    # Agent has run, same as the rest of this snapshot.
    frame: ExistingShotFrameState | None = None


class ExistingSceneState(BaseModel):
    scene_number: int
    heading: str
    time_of_day: str
    needs_review: bool
    shots: list[ExistingShotState]


class PrevisCustomizationState(BaseModel):
    title: str
    accent_color: str
    tone_note: str


class ProjectStateResponse(BaseModel):
    project_id: str
    # Added in Phase 4 — the App-Build Agent's customization step displays
    # the project's real, user-chosen title rather than having an LLM
    # re-derive one (PHASE-04-APP-BUILD-AND-CRITIC.md SS3: "the data is
    # deterministic... only the *instruction*/styling needs to be
    # LLM-authored").
    title: str
    script_id: str
    script_text: str
    style_reference: str | None
    existing_scenes: list[ExistingSceneState]
    # Added in Phase 4 — None until the App-Build Agent has written it; the
    # Critic Agent's schema check (PHASE-04-APP-BUILD-AND-CRITIC.md SS4)
    # reads it back through the same snapshot as everything else it verifies.
    previs_customization: PrevisCustomizationState | None = None


class PrevisCustomizationWriteRequest(BaseModel):
    title: str
    accent_color: str
    tone_note: str


class PrevisCustomizationWriteResponse(BaseModel):
    project_id: str
    title: str
    accent_color: str
    tone_note: str


class JobStatusUpdateRequest(BaseModel):
    status: str
    error_detail: str | None = None
    # Added in Phase 3 — optional sub-progress for the currently-running
    # stage. stage is a free-form label ("breakdown" | "frames"); the
    # frames_* counters are only sent while stage == "frames". None means
    # "no change to progress", not "reset to zero" — see JobService.update_status.
    stage: str | None = None
    frames_total: int | None = None
    frames_completed: int | None = None
    frames_failed: int | None = None
    # Added in Phase 4 — set once by the App-Build Agent when it publishes
    # the previs page; None means "no change", same convention as the
    # frames_* counters above.
    deployed_app_url: str | None = None


class JobStatusUpdateResponse(BaseModel):
    job_id: str
    status: str
    updated_at: datetime


class ShotFrameWriteRequest(BaseModel):
    image_url: str
    alt_text: str
    needs_review: bool = False


class ShotFrameWriteResponse(BaseModel):
    shot_id: str
    frame_id: str
    updated_at: datetime


class ShotEditWriteRequest(BaseModel):
    field: str
    new_value: str
    requested_by: str


class ShotEditWriteResponse(BaseModel):
    shot_id: str
    edit_id: str
    field: str
    old_value: str | None
    new_value: str
    created_at: datetime


class ShotEditSummary(BaseModel):
    shot_id: str
    field: str
    old_value: str | None
    new_value: str
    created_at: datetime


class RecentEditsResponse(BaseModel):
    edits: list[ShotEditSummary]
