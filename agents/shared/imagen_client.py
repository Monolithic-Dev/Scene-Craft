"""Image generation client — uses Gemini's multimodal generate_content (the
gemini-2.5-flash-image / "Nano Banana" model) rather than the dedicated
Imagen generate_images() API.

Two reasons, both confirmed empirically while building this phase against a
real GCP project with billing and the Vertex AI API enabled: (1)
generate_images() only works in Vertex AI mode, and this project's Imagen
publisher-model access stayed 404 even with billing/Vertex AI on — Model
Garden gates each generative-media model individually, separate from the
API-enablement step; (2) the google-genai SDK itself flags generate_images()
as deprecated and points at generate_content with image models as the
replacement. Still runs through the Vertex AI client (vertexai=True), not
the Developer API key — that's what has billing/quota attached, and the
Developer API's free tier has a 0 quota for image generation.
"""
from google import genai

from shared.config import get_settings


class ImagenClientError(Exception):
    """Raised when the model returns no usable image (safety filter, empty
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
    response = client.models.generate_content(
        model=model or settings.imagen_model,
        contents=prompt,
    )

    for candidate in response.candidates or []:
        if candidate.content is None:
            continue
        for part in candidate.content.parts or []:
            if part.inline_data is not None and part.inline_data.data:
                return bytes(part.inline_data.data)

    raise ImagenClientError("Image model returned no image data")
