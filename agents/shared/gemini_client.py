"""Thin wrapper around google-genai. Returns raw JSON text — callers own
parsing/validation against their own Pydantic schema, since a validation
failure needs to become a re-prompt with the specific error appended
(PHASE-02-BREAKDOWN-AGENT.md agent.py flow step 4), which is agent-specific
behavior, not something this generic client should hide.
"""
from google import genai
from google.genai import types
from pydantic import BaseModel

from shared.config import get_settings


class GeminiClientError(Exception):
    """Raised when Gemini returns no usable content (safety block, empty
    response) — distinct from a JSON/schema validation failure, which is
    the caller's concern once it has the text.
    """


def generate_json(
    prompt: str, response_schema: type[BaseModel], *, model: str | None = None
) -> str:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=model or settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )
    if not response.text:
        raise GeminiClientError("Gemini returned an empty response")
    return response.text


def caption_image(
    image_bytes: bytes, mime_type: str, prompt: str, *, model: str | None = None
) -> str:
    """Multimodal call for frame_agent/captioning.py — plain text output, not
    JSON, so it stays on generate_content's default text response rather
    than generate_json's schema-constrained config. Same Developer API
    client as generate_json (captioning doesn't need Vertex AI/Imagen).
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=model or settings.gemini_model,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt],
    )
    if not response.text:
        raise GeminiClientError("Gemini returned an empty caption")
    return response.text.strip()
