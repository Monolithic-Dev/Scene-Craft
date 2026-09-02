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
