"""Gemini multimodal alt-text generation — PHASE-03-FRAME-GENERATION.md SS4.

Directly satisfies the accessibility NFR in 01-PRD.md SS13; not optional
polish. Describes the generated image itself (via the real image bytes),
not the prompt used to make it, since Imagen output can diverge from what
was requested.
"""
from shared.gemini_client import caption_image

_CAPTION_PROMPT = (
    "Describe what is visible in this storyboard concept image in one "
    "screen-reader-friendly sentence. Describe the actual visual content of "
    "the image, not the prompt used to generate it — generation output can "
    "diverge from what was requested."
)


def generate_alt_text(image_bytes: bytes) -> str:
    return caption_image(image_bytes, "image/png", _CAPTION_PROMPT)
