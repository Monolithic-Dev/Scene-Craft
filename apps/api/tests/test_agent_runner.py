from unittest.mock import patch

from src.core.agent_runner import trigger_breakdown_job


def test_returns_false_and_logs_when_executable_not_configured():
    with patch("src.core.agent_runner.get_settings") as mock_settings:
        mock_settings.return_value.agents_python_executable = ""
        mock_settings.return_value.agents_working_dir = ""
        launched = trigger_breakdown_job("job-123", popen=lambda *a, **k: None)
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
        launched = trigger_breakdown_job("job-123", popen=fake_popen)

    assert launched is True
    assert calls == [[str(fake_python), "-m", "orchestrator.coordinator", "job-123"]]


def test_returns_false_when_spawn_raises_oserror():
    def failing_popen(cmd, **kwargs):
        raise OSError("no such file or directory")

    with patch("src.core.agent_runner.get_settings") as mock_settings:
        mock_settings.return_value.agents_python_executable = "python"
        mock_settings.return_value.agents_working_dir = ""
        launched = trigger_breakdown_job("job-123", popen=failing_popen)

    assert launched is False
