"""Thin wrapper around google-cloud-firestore for job_traces/{job_id}
documents — PHASE-05-ITERATION-AND-TRACE-UI.md SS2. Firestore is a fast,
ephemeral mirror of generation_jobs for the frontend's live trace panel;
Cloud SQL stays the durable system of record. Every function here is
best-effort and never raises: a Firestore outage must not break the actual
generation pipeline, which is fully Cloud-SQL-driven and functionally
complete without it — same "degrade, don't break" posture as
agent_runner.py's not-configured path.
"""
import logging
from functools import lru_cache
from typing import Any

from google.cloud import firestore

from src.core.config import get_settings

logger = logging.getLogger("scenecraft.api")

_TRACE_COLLECTION = "job_traces"


@lru_cache
def _client() -> firestore.Client | None:
    settings = get_settings()
    if not settings.google_cloud_project:
        return None
    return firestore.Client(project=settings.google_cloud_project)


def write_job_trace(job_id: str, trace: dict[str, Any]) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.collection(_TRACE_COLLECTION).document(job_id).set(trace)
    except Exception:
        logger.warning("firestore_client.write_failed", extra={"job_id": job_id}, exc_info=True)


def read_job_trace(job_id: str) -> dict[str, Any] | None:
    client = _client()
    if client is None:
        return None
    try:
        snapshot = client.collection(_TRACE_COLLECTION).document(job_id).get()
    except Exception:
        logger.warning("firestore_client.read_failed", extra={"job_id": job_id}, exc_info=True)
        return None
    return snapshot.to_dict() if snapshot.exists else None
