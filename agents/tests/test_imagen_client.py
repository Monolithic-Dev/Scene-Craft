from unittest.mock import MagicMock, patch

import pytest

from shared.imagen_client import ImagenClientError, ImagenNotConfiguredError, generate_image


def _mock_settings(project: str = "test-project"):
    settings = MagicMock()
    settings.google_cloud_project = project
    settings.google_cloud_location = "us-central1"
    settings.imagen_model = "gemini-2.5-flash-image"
    return settings


def _mock_response_with_image(image_bytes: bytes | None) -> MagicMock:
    part = MagicMock()
    part.inline_data = MagicMock(data=image_bytes) if image_bytes is not None else None
    content = MagicMock(parts=[part])
    candidate = MagicMock(content=content)
    return MagicMock(candidates=[candidate])


def test_generate_image_returns_bytes_on_success():
    mock_response = _mock_response_with_image(b"fake-png-bytes")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with (
        patch("shared.imagen_client.get_settings", return_value=_mock_settings()),
        patch("shared.imagen_client.genai.Client", return_value=mock_client) as mock_ctor,
    ):
        result = generate_image("a storyboard prompt")

    assert result == b"fake-png-bytes"
    _, kwargs = mock_ctor.call_args
    assert kwargs["vertexai"] is True
    assert kwargs["project"] == "test-project"


def test_generate_image_raises_when_not_configured():
    with patch("shared.imagen_client.get_settings", return_value=_mock_settings(project="")):
        with pytest.raises(ImagenNotConfiguredError):
            generate_image("a storyboard prompt")


def test_generate_image_raises_when_no_candidates():
    mock_response = MagicMock(candidates=[])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with (
        patch("shared.imagen_client.get_settings", return_value=_mock_settings()),
        patch("shared.imagen_client.genai.Client", return_value=mock_client),
    ):
        with pytest.raises(ImagenClientError):
            generate_image("a storyboard prompt")


def test_generate_image_raises_when_no_inline_data_in_any_part():
    text_only_part = MagicMock(inline_data=None)
    content = MagicMock(parts=[text_only_part])
    candidate = MagicMock(content=content)
    mock_response = MagicMock(candidates=[candidate])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with (
        patch("shared.imagen_client.get_settings", return_value=_mock_settings()),
        patch("shared.imagen_client.genai.Client", return_value=mock_client),
    ):
        with pytest.raises(ImagenClientError):
            generate_image("a storyboard prompt")


def test_generate_image_skips_empty_content_and_finds_image_in_later_candidate():
    empty_candidate = MagicMock(content=None)
    part = MagicMock(inline_data=MagicMock(data=b"fake-png-bytes"))
    good_candidate = MagicMock(content=MagicMock(parts=[part]))
    mock_response = MagicMock(candidates=[empty_candidate, good_candidate])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with (
        patch("shared.imagen_client.get_settings", return_value=_mock_settings()),
        patch("shared.imagen_client.genai.Client", return_value=mock_client),
    ):
        result = generate_image("a storyboard prompt")

    assert result == b"fake-png-bytes"
