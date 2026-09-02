from frame_agent.prompts import DEFAULT_STYLE_REFERENCE, build_frame_prompt


def test_frame_prompt_includes_style_reference():
    prompt = build_frame_prompt(
        action_summary="Dana stares at the water.",
        suggested_camera="wide",
        location="Ferry deck",
        time_of_day="NIGHT",
        characters=["DANA"],
        style_reference="neo-noir, high contrast",
    )
    assert "neo-noir, high contrast" in prompt


def test_frame_prompt_handles_missing_characters():
    prompt = build_frame_prompt(
        action_summary="The ferry drifts in fog.",
        suggested_camera="establishing wide",
        location="Harbor",
        time_of_day="DAWN",
        characters=[],
        style_reference="neo-noir",
    )
    assert "None" not in prompt
    assert "null" not in prompt
    assert "Characters present: none" in prompt


def test_frame_prompt_falls_back_to_default_style_when_project_has_none():
    prompt = build_frame_prompt(
        action_summary="x",
        suggested_camera="wide",
        location="y",
        time_of_day="DAY",
        characters=[],
        style_reference=None,
    )
    assert DEFAULT_STYLE_REFERENCE in prompt
