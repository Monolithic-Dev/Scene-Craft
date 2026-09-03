"""OpenTelemetry setup for apps/api. Auto-instruments FastAPI (every HTTP
request becomes a span) and SQLAlchemy (every query becomes a child span) —
see docs/Phases/PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md SS1. Agent
invocations get their own manual spans in agents/shared/telemetry.py; this
module only covers the API process's own request/DB hops.

Unconfigured by default (no OTEL_EXPORTER_OTLP_ENDPOINT env var): spans are
still created but nothing is exported — the same "stays honestly
unconfigured, never raises" convention used for Firestore/GCS elsewhere in
this codebase (see core/firestore_client.py).
"""
import os

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.engine import Engine

_SERVICE_NAME = "scenecraft-api"


def _build_provider() -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({"service.name": _SERVICE_NAME}))
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        headers_raw = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
        headers = dict(pair.split("=", 1) for pair in headers_raw.split(",") if "=" in pair)
        exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces", headers=headers)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def configure_tracing(app: FastAPI, *, engine: Engine | None = None) -> TracerProvider:
    provider = _build_provider()
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
    return provider
