"""Vertex AI Imagen client — deliberately a separate genai.Client instance
from gemini_client.py's Developer-API-mode client. google-genai's
generate_images() only works when the client is constructed in Vertex AI
mode (vertexai=True, project, location); under a plain Developer API key it
raises before making any network call ("only supported in Gemini Enterprise
Agent Platform mode"), confirmed empirically against the real SDK while
building this phase. Text/captioning calls stay on the free-tier-friendly
Developer API key — only image generation needs a billed GCP project.
"""
from google import genai
from google.genai import types

from shared.config import get_settings


class ImagenClientError(Exception):
    """Raised when Imagen returns no usable image (safety filter, empty
    response) or the API call itself fails (quota, transient error) — the
    caller (frame_agent/worker.py) is responsible for retry/backoff.
    """


class ImagenNotConfiguredError(ImagenClientError):
    """Raised when google_cloud_project isn't set — distinct so callers can
    tell "Vertex AI not set up yet" apart from "set up but broke".
    """


def generate_image(prompt: str, *, model: str | None = None) -> bytes:
    settings = get_settings()
    if not settings.google_cloud_project:
        raise ImagenNotConfiguredError(
            "google_cloud_project is not set — see agents/.env.example"
        )

    client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )
    response = client.models.generate_images(
        model=model or settings.imagen_model,
        prompt=prompt,
        config=types.GenerateImagesConfig(number_of_images=1),
    )
    if not response.generated_images:
        raise ImagenClientError("Imagen returned no images")

    image = response.generated_images[0].image
    image_bytes = image.image_bytes if image is not None else None
    if not image_bytes:
        raise ImagenClientError("Imagen returned an image with no bytes")
    return bytes(image_bytes)
