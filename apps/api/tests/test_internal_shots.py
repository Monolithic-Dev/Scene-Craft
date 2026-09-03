import io

from src.core.config import get_settings

settings = get_settings()
_HEADERS = {"X-Internal-Service-Key": settings.internal_service_key}


def _create_project_with_one_shot(client, auth_headers) -> tuple[str, str]:
    """Returns (project_id, shot_id)."""
    project = client.post(
        "/api/v1/projects", json={"title": "Midnight Ferry"}, headers=auth_headers
    ).json()
    file_content = io.BytesIO(b"INT. FERRY - NIGHT\n\nDana waits.")
    script = client.post(
        f"/api/v1/projects/{project['id']}/scripts",
        files={"file": ("script.txt", file_content, "text/plain")},
        headers=auth_headers,
    ).json()

    payload = {
        "scenes": [
            {
                "scene_number": 1,
                "heading": "INT. FERRY - NIGHT",
                "time_of_day": "NIGHT",
                "needs_review": False,
                "shots": [
                    {
                        "shot_number": 1,
                        "characters": ["DANA"],
                        "location": "Ferry deck",
                        "time_of_day": "NIGHT",
                        "action_summary": "Dana stares at the water.",
                        "suggested_camera": "wide",
                        "dialogue_snippet": None,
                    }
                ],
            }
        ]
    }
    client.post(f"/internal/v1/scripts/{script['id']}/breakdown", json=payload, headers=_HEADERS)

    state = client.get(f"/internal/v1/projects/{project['id']}/state", headers=_HEADERS).json()
    shot_id = state["existing_scenes"][0]["shots"][0]["id"]
    return project["id"], shot_id


def test_project_state_exposes_shot_id_and_needs_review(client, auth_headers):
    project_id, shot_id = _create_project_with_one_shot(client, auth_headers)
    assert shot_id  # non-empty — the Frame Agent addresses shots by this id

    state = client.get(f"/internal/v1/projects/{project_id}/state", headers=_HEADERS).json()
    shot = state["existing_scenes"][0]["shots"][0]
    assert shot["needs_review"] is False


def test_write_frame_persists_image_url_and_alt_text(client, auth_headers):
    project_id, shot_id = _create_project_with_one_shot(client, auth_headers)

    resp = client.post(
        f"/internal/v1/shots/{shot_id}/frame",
        json={"image_url": "file:///frames/shot-1.png", "alt_text": "Dana stares at the water."},
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["shot_id"] == shot_id
    assert body["frame_id"]

    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    shot = project["scenes"][0]["shots"][0]
    assert shot["frame"]["image_url"] == "file:///frames/shot-1.png"
    assert shot["frame"]["alt_text"] == "Dana stares at the water."
    assert shot["needs_review"] is False


def test_write_frame_with_needs_review_flags_the_shot(client, auth_headers):
    project_id, shot_id = _create_project_with_one_shot(client, auth_headers)

    client.post(
        f"/internal/v1/shots/{shot_id}/frame",
        json={
            "image_url": "file:///frames/placeholder.png",
            "alt_text": "Storyboard frame generation failed for this shot",
            "needs_review": True,
        },
        headers=_HEADERS,
    )

    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    shot = project["scenes"][0]["shots"][0]
    assert shot["needs_review"] is True


def test_write_frame_is_idempotent_on_the_same_shot(client, auth_headers):
    """A retried worker call overwrites the existing frame row rather than
    creating a second one — matches shot_frames.shot_id's unique constraint.
    """
    project_id, shot_id = _create_project_with_one_shot(client, auth_headers)

    client.post(
        f"/internal/v1/shots/{shot_id}/frame",
        json={"image_url": "file:///first.png", "alt_text": "first"},
        headers=_HEADERS,
    )
    resp = client.post(
        f"/internal/v1/shots/{shot_id}/frame",
        json={"image_url": "file:///second.png", "alt_text": "second"},
        headers=_HEADERS,
    )
    assert resp.status_code == 200

    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    shots = project["scenes"][0]["shots"]
    assert len(shots) == 1
    assert shots[0]["frame"]["image_url"] == "file:///second.png"


def test_write_frame_rejects_unknown_shot(client, auth_headers):
    resp = client.post(
        "/internal/v1/shots/does-not-exist/frame",
        json={"image_url": "file:///x.png", "alt_text": "x"},
        headers=_HEADERS,
    )
    assert resp.status_code == 404


def test_write_frame_requires_internal_key(client, auth_headers):
    _, shot_id = _create_project_with_one_shot(client, auth_headers)
    resp = client.post(
        f"/internal/v1/shots/{shot_id}/frame",
        json={"image_url": "file:///x.png", "alt_text": "x"},
    )
    assert resp.status_code == 401


def test_write_frame_rejects_invalid_payload(client, auth_headers):
    _, shot_id = _create_project_with_one_shot(client, auth_headers)
    resp = client.post(
        f"/internal/v1/shots/{shot_id}/frame",
        json={"alt_text": "missing image_url"},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


def _user_id(auth_headers) -> str:
    # requested_by has a real FK to users.id, so tests need an actual user
    # id, not a placeholder string — decode it straight out of the bearer
    # token rather than adding a /me endpoint just for this.
    from src.core.security import decode_access_token

    token = auth_headers["Authorization"].removeprefix("Bearer ")
    return decode_access_token(token)


def test_write_shot_edit_persists_new_value_and_audit_row(client, auth_headers):
    project_id, shot_id = _create_project_with_one_shot(client, auth_headers)
    resp = client.post(
        f"/internal/v1/shots/{shot_id}/edit",
        json={
            "field": "time_of_day",
            "new_value": "NIGHT",
            "requested_by": _user_id(auth_headers),
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["shot_id"] == shot_id
    assert body["field"] == "time_of_day"
    assert body["old_value"] == "NIGHT"  # already NIGHT from the breakdown fixture
    assert body["new_value"] == "NIGHT"

    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert project["scenes"][0]["shots"][0]["time_of_day"] == "NIGHT"


def test_write_shot_edit_updates_action_summary(client, auth_headers):
    _, shot_id = _create_project_with_one_shot(client, auth_headers)
    resp = client.post(
        f"/internal/v1/shots/{shot_id}/edit",
        json={
            "field": "action_summary",
            "new_value": "Dana grips the rail, knuckles white.",
            "requested_by": _user_id(auth_headers),
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["old_value"] == "Dana stares at the water."


def test_write_shot_edit_parses_characters_as_a_list(client, auth_headers):
    project_id, shot_id = _create_project_with_one_shot(client, auth_headers)
    resp = client.post(
        f"/internal/v1/shots/{shot_id}/edit",
        json={
            "field": "characters",
            "new_value": "DANA, RAMOS",
            "requested_by": _user_id(auth_headers),
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 200

    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert project["scenes"][0]["shots"][0]["characters"] == ["DANA", "RAMOS"]


def test_write_shot_edit_rejects_non_editable_field(client, auth_headers):
    _, shot_id = _create_project_with_one_shot(client, auth_headers)
    resp = client.post(
        f"/internal/v1/shots/{shot_id}/edit",
        json={"field": "id", "new_value": "hacked", "requested_by": "u1"},
        headers=_HEADERS,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_write_shot_edit_rejects_unknown_shot(client, auth_headers):
    resp = client.post(
        "/internal/v1/shots/does-not-exist/edit",
        json={"field": "location", "new_value": "Bridge", "requested_by": "u1"},
        headers=_HEADERS,
    )
    assert resp.status_code == 404


def test_get_edit_history_returns_recent_edits_newest_first(client, auth_headers):
    project_id, shot_id = _create_project_with_one_shot(client, auth_headers)
    user_id = _user_id(auth_headers)
    client.post(
        f"/internal/v1/shots/{shot_id}/edit",
        json={"field": "location", "new_value": "Bridge", "requested_by": user_id},
        headers=_HEADERS,
    )
    client.post(
        f"/internal/v1/shots/{shot_id}/edit",
        json={"field": "suggested_camera", "new_value": "close-up", "requested_by": user_id},
        headers=_HEADERS,
    )

    resp = client.get(f"/internal/v1/projects/{project_id}/edit-history", headers=_HEADERS)
    assert resp.status_code == 200
    edits = resp.json()["edits"]
    assert len(edits) == 2
    assert edits[0]["field"] == "suggested_camera"  # most recent first
    assert edits[1]["field"] == "location"


def test_get_edit_history_empty_for_project_with_no_edits(client, auth_headers):
    project_id, _ = _create_project_with_one_shot(client, auth_headers)
    resp = client.get(f"/internal/v1/projects/{project_id}/edit-history", headers=_HEADERS)
    assert resp.json()["edits"] == []
