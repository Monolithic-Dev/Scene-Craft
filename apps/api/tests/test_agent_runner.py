from unittest.mock import patch

from src.core.agent_runner import (
    _default_agents_dir,
    trigger_initial_generation_job,
    trigger_iteration_job,
)


def test_default_agents_dir_never_raises_regardless_of_directory_depth():
    """Regression test for a real bug found live in Cloud Run: this used to
    be a module-level constant computed eagerly at import time via
    Path(__file__).resolve().parents[4] — correct in the local dev
    checkout (4 levels up to repo root), but the deployed container's
    flattened layout (apps/api/Dockerfile's `COPY src ./src`) only nests 3
    levels deep, so parents[4] raised an uncaught IndexError that crashed
    the entire app on startup before it ever got to serve a request. Now
    lazy and exception-safe — this just asserts it never raises, in
    whatever directory depth this test happens to run from.
    """
    result = _default_agents_dir()
    assert result is None or isinstance(result, str)


def test_returns_false_and_logs_when_executable_not_configured():
    with patch("src.core.agent_runner.get_settings") as mock_settings:
        mock_settings.return_value.agents_python_executable = ""
        mock_settings.return_value.agents_working_dir = ""
        mock_settings.return_value.pubsub_topic = ""
        launched = trigger_initial_generation_job("job-123", "proj-123", popen=lambda *a, **k: None)
    assert launched is False


def test_spawns_a_process_when_executable_is_configured(tmp_path):
    fake_python = tmp_path / "python.exe"
    fake_python.write_text("")  # only needs to exist for the Path.exists() check

    calls: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        return object()

    with patch("src.core.agent_runner.get_settings") as mock_settings:
        mock_settings.return_value.agents_python_executable = str(fake_python)
        mock_settings.return_value.agents_working_dir = str(tmp_path)
        mock_settings.return_value.pubsub_topic = ""
        launched = trigger_initial_generation_job("job-123", "proj-123", popen=fake_popen)

    assert launched is True
    assert calls == [[str(fake_python), "-m", "orchestrator.coordinator", "job-123", "proj-123"]]


def test_returns_false_when_spawn_raises_oserror():
    def failing_popen(cmd, **kwargs):
        raise OSError("no such file or directory")

    with patch("src.core.agent_runner.get_settings") as mock_settings:
        mock_settings.return_value.agents_python_executable = "python"
        mock_settings.return_value.agents_working_dir = ""
        mock_settings.return_value.pubsub_topic = ""
        launched = trigger_initial_generation_job("job-123", "proj-123", popen=failing_popen)

    assert launched is False


def test_trigger_iteration_job_spawns_with_iterate_flag_and_request_text(tmp_path):
    fake_python = tmp_path / "python.exe"
    fake_python.write_text("")

    calls: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        return object()

    with patch("src.core.agent_runner.get_settings") as mock_settings:
        mock_settings.return_value.agents_python_executable = str(fake_python)
        mock_settings.return_value.agents_working_dir = str(tmp_path)
        mock_settings.return_value.pubsub_topic = ""
        launched = trigger_iteration_job(
            "job-123", "proj-123", "make scene 4 night-time", "user-1", popen=fake_popen
        )

    assert launched is True
    assert calls == [
        [
            str(fake_python),
            "-m",
            "orchestrator.coordinator",
            "--iterate",
            "job-123",
            "proj-123",
            "make scene 4 night-time",
            "user-1",
        ]
    ]


def test_trigger_iteration_job_returns_false_when_not_configured():
    with patch("src.core.agent_runner.get_settings") as mock_settings:
        mock_settings.return_value.agents_python_executable = ""
        mock_settings.return_value.agents_working_dir = ""
        mock_settings.return_value.pubsub_topic = ""
        launched = trigger_iteration_job(
            "job-123", "proj-123", "make it night", "user-1", popen=lambda *a, **k: None
        )
    assert launched is False


# --- Pub/Sub dispatch path (Phase 6) ----------------------------------------


class _FakePublisherClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []

    def publish(self, topic: str, data: bytes) -> None:
        self.published.append((topic, data))


def test_trigger_initial_generation_publishes_when_pubsub_topic_configured():
    fake_client = _FakePublisherClient()

    with patch("src.core.agent_runner.get_settings") as mock_settings:
        mock_settings.return_value.pubsub_topic = "projects/p/topics/jobs"
        launched = trigger_initial_generation_job(
            "job-123", "proj-123", publisher=lambda: fake_client
        )

    assert launched is True
    assert len(fake_client.published) == 1
    topic, data = fake_client.published[0]
    assert topic == "projects/p/topics/jobs"
    import json

    assert json.loads(data) == {
        "job_type": "initial_generation",
        "job_id": "job-123",
        "project_id": "proj-123",
    }


def test_trigger_iteration_job_publishes_when_pubsub_topic_configured():
    fake_client = _FakePublisherClient()

    with patch("src.core.agent_runner.get_settings") as mock_settings:
        mock_settings.return_value.pubsub_topic = "projects/p/topics/jobs"
        launched = trigger_iteration_job(
            "job-123",
            "proj-123",
            "make scene 4 night-time",
            "user-1",
            publisher=lambda: fake_client,
        )

    assert launched is True
    topic, data = fake_client.published[0]
    import json

    assert json.loads(data) == {
        "job_type": "iteration",
        "job_id": "job-123",
        "project_id": "proj-123",
        "user_request": "make scene 4 night-time",
        "requested_by": "user-1",
    }


def test_trigger_initial_generation_returns_false_when_publish_raises():
    class _RaisingClient:
        def publish(self, topic, data):
            raise RuntimeError("pubsub unavailable")

    with patch("src.core.agent_runner.get_settings") as mock_settings:
        mock_settings.return_value.pubsub_topic = "projects/p/topics/jobs"
        launched = trigger_initial_generation_job(
            "job-123", "proj-123", publisher=lambda: _RaisingClient()
        )

    assert launched is False
