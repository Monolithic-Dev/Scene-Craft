from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from shared.gemini_client import GeminiClientError, generate_json


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
