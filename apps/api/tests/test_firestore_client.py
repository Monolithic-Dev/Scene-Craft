"""google-cloud-firestore itself is mocked — these tests cover
firestore_client.py's own logic: the not-configured no-op path and the
best-effort (never-raise) error handling, per its own docstring.
"""
from unittest.mock import MagicMock, patch

import pytest

from src.core.firestore_client import _client, read_job_trace, write_job_trace


@pytest.fixture(autouse=True)
def _clear_client_cache():
    # _client() is @lru_cache'd (a deliberate singleton in production — see
    # its docstring), which would otherwise let whichever test runs first
    # decide every later test's cached result regardless of that test's own
    # get_settings mock.
    _client.cache_clear()
    yield
    _client.cache_clear()


def test_write_job_trace_is_a_noop_when_not_configured():
    with patch("src.core.firestore_client.get_settings") as mock_settings:
        mock_settings.return_value.google_cloud_project = ""
        with patch("src.core.firestore_client.firestore.Client") as mock_client_cls:
            write_job_trace("job-1", {"status": "running"})
    mock_client_cls.assert_not_called()


def test_read_job_trace_returns_none_when_not_configured():
    with patch("src.core.firestore_client.get_settings") as mock_settings:
        mock_settings.return_value.google_cloud_project = ""
        result = read_job_trace("job-1")
    assert result is None


def test_write_job_trace_calls_set_on_the_document():
    mock_doc = MagicMock()
    mock_client = MagicMock()
    mock_client.collection.return_value.document.return_value = mock_doc

    with (
        patch("src.core.firestore_client._client", return_value=mock_client),
    ):
        write_job_trace("job-1", {"status": "running"})

    mock_client.collection.assert_called_once_with("job_traces")
    mock_client.collection.return_value.document.assert_called_once_with("job-1")
    mock_doc.set.assert_called_once_with({"status": "running"})


def test_write_job_trace_swallows_exceptions():
    mock_client = MagicMock()
    mock_client.collection.return_value.document.return_value.set.side_effect = RuntimeError("x")

    with patch("src.core.firestore_client._client", return_value=mock_client):
        write_job_trace("job-1", {"status": "running"})  # must not raise


def test_read_job_trace_returns_dict_when_document_exists():
    mock_snapshot = MagicMock(exists=True)
    mock_snapshot.to_dict.return_value = {"status": "complete"}
    mock_client = MagicMock()
    mock_client.collection.return_value.document.return_value.get.return_value = mock_snapshot

    with patch("src.core.firestore_client._client", return_value=mock_client):
        result = read_job_trace("job-1")

    assert result == {"status": "complete"}


def test_read_job_trace_returns_none_when_document_missing():
    mock_snapshot = MagicMock(exists=False)
    mock_client = MagicMock()
    mock_client.collection.return_value.document.return_value.get.return_value = mock_snapshot

    with patch("src.core.firestore_client._client", return_value=mock_client):
        result = read_job_trace("job-1")

    assert result is None


def test_read_job_trace_swallows_exceptions_and_returns_none():
    mock_client = MagicMock()
    mock_client.collection.return_value.document.return_value.get.side_effect = RuntimeError("x")

    with patch("src.core.firestore_client._client", return_value=mock_client):
        result = read_job_trace("job-1")

    assert result is None
