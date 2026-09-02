from unittest.mock import MagicMock, patch

import pytest

from shared.imagen_client import ImagenClientError, ImagenNotConfiguredError, generate_image


def _mock_settings(project: str = "test-project"):
    settings = MagicMock()
    settings.google_cloud_project = project
    settings.google_cloud_location = "us-central1"
    settings.imagen_model = "imagen-4.0-generate-001"
    return settings


def test_generate_image_returns_bytes_on_success():
    mock_image = MagicMock(image_bytes=b"fake-png-bytes")
    mock_generated = MagicMock(image=mock_image)
    mock_response = MagicMock(generated_images=[mock_generated])
    mock_client = MagicMock()
    mock_client.models.generate_images.return_value = mock_response

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


def test_generate_image_raises_when_no_images_returned():
    mock_response = MagicMock(generated_images=[])
    mock_client = MagicMock()
    mock_client.models.generate_images.return_value = mock_response

    with (
        patch("shared.imagen_client.get_settings", return_value=_mock_settings()),
        patch("shared.imagen_client.genai.Client", return_value=mock_client),
    ):
        with pytest.raises(ImagenClientError):
            generate_image("a storyboard prompt")


def test_generate_image_raises_when_image_has_no_bytes():
    mock_image = MagicMock(image_bytes=None)
    mock_generated = MagicMock(image=mock_image)
    mock_response = MagicMock(generated_images=[mock_generated])
    mock_client = MagicMock()
    mock_client.models.generate_images.return_value = mock_response

    with (
        patch("shared.imagen_client.get_settings", return_value=_mock_settings()),
        patch("shared.imagen_client.genai.Client", return_value=mock_client),
    ):
        with pytest.raises(ImagenClientError):
            generate_image("a storyboard prompt")
