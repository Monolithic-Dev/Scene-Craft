import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.internal.router import internal_router
from src.api.v1.router import api_router
from src.core.config import get_settings
from src.core.database import engine
from src.core.exceptions import DomainError
from src.core.logging_config import configure_logging
from src.core.rate_limiter import RateLimiter, rate_limit_key
from src.core.telemetry import configure_tracing

settings = get_settings()
configure_logging()
logger = logging.getLogger("scenecraft.api")

app = FastAPI(
    title="SceneCraft API",
    version="0.1.0",
    description="Control-plane API for the SceneCraft agentic previs studio.",
)

# Instrumenting HTTP + DB spans before any middleware/routes are hit, so
# every request gets one from the start. See core/telemetry.py — a no-op
# exporter until OTEL_EXPORTER_OTLP_ENDPOINT is set.
configure_tracing(app, engine=engine)

# Held on app.state (rather than a module-level singleton) so tests can
# swap in a fakeredis-backed instance per test without patching internals —
# see tests/conftest.py.
app.state.rate_limiter = RateLimiter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# --- Distributed rate limiting (Redis-backed, shared across instances) -----
# Phase 1 shipped an in-process, IP-keyed sliding-window limiter explicitly
# flagged as temporary (docs/Phases/PHASE-01-FOUNDATIONS.md pitfall #5).
# This replaces it — see core/rate_limiter.py for the algorithm and the
# user-id-when-authenticated / IP-otherwise keying rationale.
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next: Any) -> Any:
    limiter: RateLimiter = request.app.state.rate_limiter
    key = rate_limit_key(
        request.headers.get("authorization"),
        request.client.host if request.client else None,
    )
    if not limiter.allow(key, limit=settings.rate_limit_requests_per_minute):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": {"code": "RATE_LIMITED", "message": "Too many requests, slow down."}},
        )
    return await call_next(request)


# --- Consistent error envelope for all domain errors -----------------------
@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    logger.warning("domain_error", extra={"code": exc.code, "path": request.url.path})
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": str(exc)}},
    )


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)
app.include_router(internal_router)
