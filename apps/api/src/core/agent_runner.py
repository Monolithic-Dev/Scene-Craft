"""Trigger for the agent orchestrator — two mechanisms, selected by config.

**Local dev (default):** subprocess.Popen, exactly as in Phases 2-5.
agents/ is a separate installable package with its own dependencies (mcp,
google-genai) that must not be installed into apps/api's own venv, so this
cannot be an in-process function call — it has to be a separate OS process.

**Deployed (Phase 6, when settings.pubsub_topic is set):** publishes a
Pub/Sub message instead. The "Agent Workers" Cloud Run service
(agents/orchestrator/pubsub_receiver.py) receives it via push subscription
and calls straight into the same run_initial_generation()/run_iteration()
functions the subprocess path's CLI entrypoint uses — see
docs/Phases/PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md and
10-DIAGRAMS.md SS8.

If neither is configured (AGENTS_PYTHON_EXECUTABLE unset locally, or
pubsub_topic unset in a deployed environment without it), the job is left
QUEUED and a warning is logged — a stalled-but-honest job is better than
silently pretending it ran.
"""
import json
import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from shutil import which
from typing import Any

from src.core.config import get_settings

logger = logging.getLogger("scenecraft.api")

# repo_root/agents — apps/api/src/core/agent_runner.py -> parents[4] is repo root.
_DEFAULT_AGENTS_DIR = Path(__file__).resolve().parents[4] / "agents"

PopenFactory = Callable[..., subprocess.Popen[bytes]]
PublisherFactory = Callable[[], Any]


def _resolve_python_executable(configured: str) -> str | None:
    if not configured:
        return None
    if Path(configured).exists():
        return configured
    return which(configured)


def _publish_job(payload: dict[str, Any], *, publisher: PublisherFactory | None) -> bool:
    """Publishes payload to settings.pubsub_topic. publisher, if given, must
    be a zero-arg callable returning an object with .publish(topic, data)
    (matching google.cloud.pubsub_v1.PublisherClient's call shape) — tests
    inject a fake one the same way trigger_*_job's popen param works.
    """
    settings = get_settings()
    from google.cloud.pubsub_v1 import PublisherClient  # heavy import, only paid when used

    client = publisher() if publisher is not None else PublisherClient()
    topic_path = settings.pubsub_topic
    try:
        client.publish(topic_path, json.dumps(payload).encode("utf-8"))
    except Exception:
        logger.exception("agent_runner.publish_failed", extra={"payload": payload})
        return False
    return True


def trigger_initial_generation_job(
    job_id: str,
    project_id: str,
    *,
    popen: PopenFactory = subprocess.Popen,
    publisher: PublisherFactory | None = None,
) -> bool:
    """Best-effort dispatch of the orchestrator for the given job. Returns
    whether it was actually dispatched (tests assert on this instead of on
    process completion, since that depends on a live Gemini key).

    project_id travels alongside job_id because the orchestrator's only
    other way to learn it would be reading generation_jobs directly — and
    agents never get direct DB access, only MCP. Cheaper to just pass it.
    """
    settings = get_settings()
    if settings.pubsub_topic:
        return _publish_job(
            {"job_type": "initial_generation", "job_id": job_id, "project_id": project_id},
            publisher=publisher,
        )

    python_executable = _resolve_python_executable(settings.agents_python_executable)
    if python_executable is None:
        logger.warning(
            "agent_runner.not_configured",
            extra={"job_id": job_id, "hint": "set AGENTS_PYTHON_EXECUTABLE to run Phase 2+ jobs"},
        )
        return False

    agents_dir = settings.agents_working_dir or str(_DEFAULT_AGENTS_DIR)
    try:
        popen(
            [python_executable, "-m", "orchestrator.coordinator", job_id, project_id],
            cwd=agents_dir,
        )
    except OSError:
        logger.exception("agent_runner.spawn_failed", extra={"job_id": job_id})
        return False
    return True


def trigger_iteration_job(
    job_id: str,
    project_id: str,
    user_request: str,
    requested_by: str,
    *,
    popen: PopenFactory = subprocess.Popen,
    publisher: PublisherFactory | None = None,
) -> bool:
    """Same dispatch mechanism as trigger_initial_generation_job, for
    job_type == iteration — see PHASE-05-ITERATION-AND-TRACE-UI.md SS5. The
    director's free-text request and their user id (ShotEdit.requested_by
    has a real FK to users.id) travel as plain data — never through a shell
    (popen's list form passes each element literally, and the Pub/Sub
    payload is JSON, so there's no injection surface from arbitrary user
    text either way) — since the Iteration Agent's only other way to learn
    either would be a DB column dedicated to one job type, which isn't
    worth adding for this.
    """
    settings = get_settings()
    if settings.pubsub_topic:
        return _publish_job(
            {
                "job_type": "iteration",
                "job_id": job_id,
                "project_id": project_id,
                "user_request": user_request,
                "requested_by": requested_by,
            },
            publisher=publisher,
        )

    python_executable = _resolve_python_executable(settings.agents_python_executable)
    if python_executable is None:
        logger.warning(
            "agent_runner.not_configured",
            extra={"job_id": job_id, "hint": "set AGENTS_PYTHON_EXECUTABLE to run Phase 2+ jobs"},
        )
        return False

    agents_dir = settings.agents_working_dir or str(_DEFAULT_AGENTS_DIR)
    try:
        popen(
            [
                python_executable,
                "-m",
                "orchestrator.coordinator",
                "--iterate",
                job_id,
                project_id,
                user_request,
                requested_by,
            ],
            cwd=agents_dir,
        )
    except OSError:
        logger.exception("agent_runner.spawn_failed", extra={"job_id": job_id})
        return False
    return True
