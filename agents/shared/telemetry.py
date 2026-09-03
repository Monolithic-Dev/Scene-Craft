"""OpenTelemetry tracing for the agents process.

One TracerProvider per orchestrator run (each job is its own subprocess or
Pub/Sub-push request — see orchestrator/coordinator.py and
orchestrator/pubsub_receiver.py). Unconfigured by default (no
OTEL_EXPORTER_OTLP_ENDPOINT env var): spans are still created and can be
inspected in-process (tests use this), but nothing is exported anywhere —
the same "stays honestly unconfigured, never raises" convention used for
Firestore/GCS elsewhere in this codebase (see
apps/api/src/core/firestore_client.py).

See docs/Phases/PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md SS1 for the
required span name/attribute contract that agent_span() implements.
"""
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace import Span, Tracer

_SERVICE_NAME = "scenecraft-agents"
_provider: TracerProvider | None = None


def _build_default_provider() -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({"service.name": _SERVICE_NAME}))
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if endpoint:
        # Imported lazily so the OTLP exporter's own deps aren't required
        # for a process that never configures an endpoint (e.g. local dev).
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        headers_raw = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
        headers = dict(pair.split("=", 1) for pair in headers_raw.split(",") if "=" in pair)
        exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces", headers=headers)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def get_tracer() -> Tracer:
    global _provider
    if _provider is None:
        _provider = _build_default_provider()
    return _provider.get_tracer(_SERVICE_NAME)


def configure_for_testing(exporter: SpanExporter) -> None:
    """Test-only hook: point subsequent get_tracer() calls at a fresh
    provider wired to the given exporter (typically an InMemorySpanExporter)
    so tests can assert on emitted spans without a real OTLP endpoint.
    """
    global _provider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    _provider = TracerProvider(resource=Resource.create({"service.name": _SERVICE_NAME}))
    _provider.add_span_processor(SimpleSpanProcessor(exporter))


def reset_for_testing() -> None:
    """Test-only hook: drop the cached provider so the next get_tracer()
    call rebuilds from the current environment (or the default no-export
    provider, if a test left OTEL_EXPORTER_OTLP_ENDPOINT unset)."""
    global _provider
    _provider = None


@asynccontextmanager
async def agent_span(
    agent_name: str, *, project_id: str, job_id: str, attempt: int = 1
) -> AsyncIterator[Span]:
    """Wraps one agent invocation with the span name/attribute contract from
    PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md SS1
    ("agent.<agent_name>.run", project_id/job_id/agent_name/status/
    duration_ms). status defaults to "success"; callers can override it to
    "retry" from inside the `async with` block (e.g. after inspecting a
    Critic verdict) without that being clobbered on normal exit. On an
    uncaught exception, status is forced to "failure", the exception is
    recorded on the span, and it's re-raised unchanged — every existing
    try/except around the wrapped `await run_x(...)` call keeps working
    exactly as before.

    tool_calls_count/token_usage from the phase doc's attribute set are
    deliberately omitted: no agent result currently threads that data back
    to the Coordinator (see PHASE-06 implementation notes) — a known,
    documented gap rather than a fabricated value.
    """
    tracer = get_tracer()
    start = time.monotonic()
    with tracer.start_as_current_span(
        f"agent.{agent_name}.run",
        attributes={
            "project_id": project_id,
            "job_id": job_id,
            "agent_name": agent_name,
            "attempt": attempt,
            "status": "success",
        },
    ) as span:
        try:
            yield span
        except Exception:
            # start_as_current_span already records the exception as a span
            # event and sets the span's OTel status to ERROR by default
            # once it propagates out of this `with` block below (record_
            # exception=True, set_status_on_exception=True) — doing either
            # again here would double up the recorded event. Only the
            # custom "status" attribute (success|failure|retry) is ours.
            span.set_attribute("status", "failure")
            raise
        finally:
            span.set_attribute("duration_ms", round((time.monotonic() - start) * 1000, 2))
