from unittest.mock import MagicMock, patch

from shared.storage import store_frame


def test_store_frame_writes_bytes_and_returns_a_file_uri(tmp_path):
    settings = MagicMock(local_storage_dir=str(tmp_path))
    with patch("shared.storage.get_settings", return_value=settings):
        url = store_frame("proj-1", "shot-1", b"fake-png-bytes")

    assert url.startswith("file:")
    assert url.endswith("shot-1.png")

    written = tmp_path / "frames" / "proj-1" / "shot-1.png"
    assert written.read_bytes() == b"fake-png-bytes"


def test_store_frame_creates_a_separate_file_per_project_and_shot(tmp_path):
    settings = MagicMock(local_storage_dir=str(tmp_path))
    with patch("shared.storage.get_settings", return_value=settings):
        store_frame("proj-1", "shot-1", b"one")
        store_frame("proj-1", "shot-2", b"two")
        store_frame("proj-2", "shot-1", b"three")

    assert (tmp_path / "frames" / "proj-1" / "shot-1.png").read_bytes() == b"one"
    assert (tmp_path / "frames" / "proj-1" / "shot-2.png").read_bytes() == b"two"
    assert (tmp_path / "frames" / "proj-2" / "shot-1.png").read_bytes() == b"three"


def test_store_frame_overwrites_on_regeneration(tmp_path):
    settings = MagicMock(local_storage_dir=str(tmp_path))
    with patch("shared.storage.get_settings", return_value=settings):
        store_frame("proj-1", "shot-1", b"first")
        store_frame("proj-1", "shot-1", b"second")

    assert (tmp_path / "frames" / "proj-1" / "shot-1.png").read_bytes() == b"second"
