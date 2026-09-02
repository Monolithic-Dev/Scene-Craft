from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from shared.gemini_client import GeminiClientError, caption_image, generate_json


class _Schema(BaseModel):
    x: int


def test_generate_json_returns_response_text():
    mock_response = MagicMock(text='{"x": 1}')
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("shared.gemini_client.genai.Client", return_value=mock_client):
        result = generate_json("prompt", _Schema)

    assert result == '{"x": 1}'


def test_generate_json_passes_the_response_schema_through():
    mock_response = MagicMock(text='{"x": 1}')
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("shared.gemini_client.genai.Client", return_value=mock_client):
        generate_json("prompt", _Schema)

    _, kwargs = mock_client.models.generate_content.call_args
    assert kwargs["config"].response_schema is _Schema
    assert kwargs["config"].response_mime_type == "application/json"


def test_generate_json_raises_on_empty_response():
    mock_response = MagicMock(text=None)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("shared.gemini_client.genai.Client", return_value=mock_client):
        with pytest.raises(GeminiClientError):
            generate_json("prompt", _Schema)


def test_caption_image_returns_stripped_response_text():
    mock_response = MagicMock(text="  A director stares out at the water.  \n")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("shared.gemini_client.genai.Client", return_value=mock_client):
        result = caption_image(b"fake-png-bytes", "image/png", "describe this")

    assert result == "A director stares out at the water."


def test_caption_image_sends_image_bytes_and_mime_type():
    mock_response = MagicMock(text="a caption")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("shared.gemini_client.genai.Client", return_value=mock_client):
        caption_image(b"fake-png-bytes", "image/png", "describe this")

    _, kwargs = mock_client.models.generate_content.call_args
    image_part = kwargs["contents"][0]
    assert image_part.inline_data.data == b"fake-png-bytes"
    assert image_part.inline_data.mime_type == "image/png"
    assert kwargs["contents"][1] == "describe this"


def test_caption_image_raises_on_empty_response():
    mock_response = MagicMock(text="")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("shared.gemini_client.genai.Client", return_value=mock_client):
        with pytest.raises(GeminiClientError):
            caption_image(b"fake-png-bytes", "image/png", "describe this")
