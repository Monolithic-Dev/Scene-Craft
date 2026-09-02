"""Shared test doubles. Real DB/HTTP/stdio access is out of scope for these
tests — per 09-CODING-STANDARDS.md SS4, agent tool calls are tested against
mocked external APIs; mcp_server and apps/api each have their own real
integration tests for the transport/DB layers this stands in for.
"""
import pytest


class FakeMcp:
    def __init__(
        self,
        script_text: str,
        *,
        script_id: str = "script-1",
        project_id: str = "proj-1",
        style_reference: str | None = None,
        existing_scenes: list[dict] | None = None,
    ) -> None:
        self.script_text = script_text
        self.script_id = script_id
        self.project_id = project_id
        self.style_reference = style_reference
        self.existing_scenes = existing_scenes or []
        self.written_scenes: list[dict] = []
        self.written_frames: list[dict] = []
        # Each entry is a dict so callers can add keyword-only progress
        # fields without every existing assertion needing a wider tuple.
        self.job_statuses: list[dict] = []

    async def get_project_state(self, project_id: str) -> dict:
        assert project_id == self.project_id
        return {
            "project_id": self.project_id,
            "script_id": self.script_id,
            "script_text": self.script_text,
            "style_reference": self.style_reference,
            "existing_scenes": self.existing_scenes,
        }

    async def write_shot_records(self, script_id: str, scenes: list[dict]) -> dict:
        assert script_id == self.script_id
        self.written_scenes.extend(scenes)
        return {
            "scenes_written": len(scenes),
            "shots_written": sum(len(s["shots"]) for s in scenes),
        }

    async def write_frame_record(
        self, shot_id: str, image_url: str, alt_text: str, *, needs_review: bool = False
    ) -> dict:
        self.written_frames.append(
            {
                "shot_id": shot_id,
                "image_url": image_url,
                "alt_text": alt_text,
                "needs_review": needs_review,
            }
        )
        return {
            "shot_id": shot_id,
            "frame_id": f"frame-{len(self.written_frames)}",
            "updated_at": "2026-01-01T00:00:00Z",
        }

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        error_detail: str | None = None,
        *,
        stage: str | None = None,
        frames_total: int | None = None,
        frames_completed: int | None = None,
        frames_failed: int | None = None,
    ) -> dict:
        self.job_statuses.append(
            {
                "status": status,
                "error_detail": error_detail,
                "stage": stage,
                "frames_total": frames_total,
                "frames_completed": frames_completed,
                "frames_failed": frames_failed,
            }
        )
        return {"job_id": job_id, "status": status, "updated_at": "2026-01-01T00:00:00Z"}


@pytest.fixture
def fake_mcp() -> FakeMcp:
    return FakeMcp(script_text="")
