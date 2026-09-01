"""Local-dev trigger for the agent orchestrator.

Phase 2-5 stand-in for the real mechanism: a Pub/Sub message picked up by a
Cloud Run job, provisioned in Phase 6 (see
docs/Phases/PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md). agents/ is a
separate installable package with its own dependencies (mcp, google-genai)
that must not be installed into apps/api's own venv, so this cannot be an
in-process function call — it has to be a separate OS process, exactly as
it will be in production, just spawned locally instead of by Cloud Run.

If the agents environment isn't configured (AGENTS_PYTHON_EXECUTABLE unset,
or the interpreter doesn't exist), the job is left QUEUED and a warning is
logged — a stalled-but-honest job is better than silently pretending it ran.
"""
import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from shutil import which

from src.core.config import get_settings

logger = logging.getLogger("scenecraft.api")

# repo_root/agents — apps/api/src/core/agent_runner.py -> parents[4] is repo root.
_DEFAULT_AGENTS_DIR = Path(__file__).resolve().parents[4] / "agents"

PopenFactory = Callable[..., subprocess.Popen[bytes]]


def _resolve_python_executable(configured: str) -> str | None:
    if not configured:
        return None
    if Path(configured).exists():
        return configured
    return which(configured)


def trigger_breakdown_job(
    job_id: str,
    project_id: str,
    *,
    popen: PopenFactory = subprocess.Popen,
) -> bool:
    """Best-effort spawn of the orchestrator for the given job. Returns
    whether a process was actually launched (tests assert on this instead
    of on process completion, since that depends on a live Gemini key).

    project_id travels alongside job_id because the orchestrator's only
    other way to learn it would be reading generation_jobs directly — and
    agents never get direct DB access, only MCP. Cheaper to just pass it.
    """
    settings = get_settings()
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
