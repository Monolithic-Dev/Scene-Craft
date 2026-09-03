import io

from src.core.config import get_settings

settings = get_settings()
_HEADERS = {"X-Internal-Service-Key": settings.internal_service_key}


def _create_project_with_script(client, auth_headers) -> tuple[str, str]:
    project = client.post(
        "/api/v1/projects", json={"title": "Midnight Ferry"}, headers=auth_headers
    ).json()
    file_content = io.BytesIO(b"INT. FERRY - NIGHT\n\nDana waits.")
    script = client.post(
        f"/api/v1/projects/{project['id']}/scripts",
        files={"file": ("script.txt", file_content, "text/plain")},
        headers=auth_headers,
    ).json()
    return project["id"], script["id"]


def test_internal_routes_reject_missing_key(client, auth_headers):
    project_id, _ = _create_project_with_script(client, auth_headers)
    resp = client.get(f"/internal/v1/projects/{project_id}/state")
    assert resp.status_code == 401


def test_internal_routes_reject_wrong_key(client, auth_headers):
    project_id, _ = _create_project_with_script(client, auth_headers)
    resp = client.get(
        f"/internal/v1/projects/{project_id}/state",
        headers={"X-Internal-Service-Key": "wrong-key"},
    )
    assert resp.status_code == 401


def test_get_project_state_returns_expected_shape(client, auth_headers):
    project_id, script_id = _create_project_with_script(client, auth_headers)
    resp = client.get(f"/internal/v1/projects/{project_id}/state", headers=_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == project_id
    assert body["script_id"] == script_id
    assert "Dana waits" in body["script_text"]
    assert body["existing_scenes"] == []


def test_write_breakdown_persists_scenes_and_shots(client, auth_headers):
    project_id, script_id = _create_project_with_script(client, auth_headers)
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
    resp = client.post(
        f"/internal/v1/scripts/{script_id}/breakdown", json=payload, headers=_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json() == {"scenes_written": 1, "shots_written": 1}

    state = client.get(f"/internal/v1/projects/{project_id}/state", headers=_HEADERS).json()
    assert len(state["existing_scenes"]) == 1
    assert state["existing_scenes"][0]["shots"][0]["location"] == "Ferry deck"


def test_write_breakdown_rejects_invalid_payload(client, auth_headers):
    _, script_id = _create_project_with_script(client, auth_headers)
    # Missing every required shot field fails Pydantic validation before it
    # ever reaches BreakdownService — not silently coerced.
    resp = client.post(
        f"/internal/v1/scripts/{script_id}/breakdown",
        json={"scenes": [{"scene_number": 1, "heading": "X", "shots": [{"shot_number": 1}]}]},
        headers=_HEADERS,
    )
    assert resp.status_code == 422


def test_write_breakdown_rejects_unknown_script(client, auth_headers):
    resp = client.post(
        "/internal/v1/scripts/does-not-exist/breakdown", json={"scenes": []}, headers=_HEADERS
    )
    assert resp.status_code == 404


def test_get_project_state_for_unknown_project_is_not_found(client, auth_headers):
    resp = client.get("/internal/v1/projects/does-not-exist/state", headers=_HEADERS)
    assert resp.status_code == 404


def test_get_project_state_includes_frame_once_written(client, auth_headers):
    """The App-Build/Critic Agents read frame coverage off the same
    get_project_state snapshot as everything else — PHASE-04-APP-BUILD-AND-
    CRITIC.md SS4.
    """
    project_id, script_id = _create_project_with_script(client, auth_headers)
    payload = {
        "scenes": [
            {
                "scene_number": 1,
                "heading": "INT. FERRY - NIGHT",
                "shots": [
                    {
                        "shot_number": 1,
                        "location": "Ferry deck",
                        "action_summary": "Dana stares at the water.",
                        "suggested_camera": "wide",
                    }
                ],
            }
        ]
    }
    client.post(f"/internal/v1/scripts/{script_id}/breakdown", json=payload, headers=_HEADERS)
    state = client.get(f"/internal/v1/projects/{project_id}/state", headers=_HEADERS).json()
    shot = state["existing_scenes"][0]["shots"][0]
    assert shot["frame"] is None

    shot_id = shot["id"]
    client.post(
        f"/internal/v1/shots/{shot_id}/frame",
        json={"image_url": "file:///a.png", "alt_text": "Dana stares at the water."},
        headers=_HEADERS,
    )
    state = client.get(f"/internal/v1/projects/{project_id}/state", headers=_HEADERS).json()
    shot = state["existing_scenes"][0]["shots"][0]
    assert shot["frame"] == {"image_url": "file:///a.png", "alt_text": "Dana stares at the water."}


def test_get_project_state_previs_customization_is_none_until_written(client, auth_headers):
    project_id, _ = _create_project_with_script(client, auth_headers)
    state = client.get(f"/internal/v1/projects/{project_id}/state", headers=_HEADERS).json()
    assert state["previs_customization"] is None


def test_write_previs_customization_persists_and_is_readable_back(client, auth_headers):
    project_id, _ = _create_project_with_script(client, auth_headers)
    resp = client.post(
        f"/internal/v1/projects/{project_id}/previs-customization",
        json={
            "title": "Midnight Ferry",
            "accent_color": "#ff6a00",
            "tone_note": "Tense, nocturnal",
        },
        headers=_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "project_id": project_id,
        "title": "Midnight Ferry",
        "accent_color": "#ff6a00",
        "tone_note": "Tense, nocturnal",
    }

    state = client.get(f"/internal/v1/projects/{project_id}/state", headers=_HEADERS).json()
    assert state["previs_customization"] == {
        "title": "Midnight Ferry",
        "accent_color": "#ff6a00",
        "tone_note": "Tense, nocturnal",
    }


def test_write_previs_customization_rejects_unknown_project(client, auth_headers):
    resp = client.post(
        "/internal/v1/projects/does-not-exist/previs-customization",
        json={"title": "X", "accent_color": "#000000", "tone_note": "Y"},
        headers=_HEADERS,
    )
    assert resp.status_code == 404
