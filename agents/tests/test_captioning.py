from unittest.mock import patch

from frame_agent.captioning import generate_alt_text


def test_generate_alt_text_calls_caption_image_with_png_mime_type():
    with patch(
        "frame_agent.captioning.caption_image", return_value="Dana stares at the water."
    ) as mock_caption:
        result = generate_alt_text(b"fake-png-bytes")

    assert result == "Dana stares at the water."
    args, _ = mock_caption.call_args
    assert args[0] == b"fake-png-bytes"
    assert args[1] == "image/png"
    assert "actual visual content" in args[2]
