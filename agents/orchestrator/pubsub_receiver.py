"""Cloud Run entrypoint for the "Agent Workers" service (10-DIAGRAMS.md SS8's
CR3). Receives Pub/Sub push messages published by
apps/api/src/core/agent_runner.py's _publish_job() and calls straight into
run_initial_generation()/run_iteration() in-process — no subprocess, no CLI
re-entry, since a Cloud Run service is already a dedicated process per
request rather than something apps/api spawns locally.

orchestrator.coordinator's CLI entrypoint (`python -m
orchestrator.coordinator ...`) is unchanged and still what local dev uses;
this module is the deployed alternative, selected by which container image
runs it (see agents/Dockerfile).

Pub/Sub push request shape (https://cloud.google.com/pubsub/docs/push):
{"message": {"data": "<base64 JSON>", "messageId": "...", ...},
 "subscription": "..."}
"""
import base64
import json
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from orchestrator.coordinator import run_initial_generation, run_iteration

logger = logging.getLogger("scenecraft.orchestrator")

app = FastAPI(title="SceneCraft Agent Workers")


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _decode_push_payload(body: dict[str, Any]) -> dict[str, Any]:
    message = body["message"]
    data = base64.b64decode(message["data"]).decode("utf-8")
    payload: dict[str, Any] = json.loads(data)
    return payload


@app.post("/pubsub/push")
async def pubsub_push(request: Request) -> JSONResponse:
    body = await request.json()
    try:
        payload = _decode_push_payload(body)
    except (KeyError, ValueError) as exc:
        # A malformed push envelope is never retryable into correctness —
        # ack it (2xx) so Pub/Sub stops redelivering, but log loudly, per
        # the same "fail loud, never fail silent" standard as the
        # Coordinator's own stage-boundary handling.
        logger.error("pubsub_receiver.malformed_payload", extra={"error": str(exc)})
        return JSONResponse(status_code=200, content={"status": "ignored_malformed"})

    job_type = payload.get("job_type")
    job_id = payload["job_id"]
    project_id = payload["project_id"]

    if job_type == "iteration":
        await run_iteration(
            job_id, project_id, payload["user_request"], payload["requested_by"]
        )
    else:
        await run_initial_generation(job_id, project_id)

    return JSONResponse(status_code=200, content={"status": "processed", "job_id": job_id})
