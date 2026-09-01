import logging
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.internal.router import internal_router
from src.api.v1.router import api_router
from src.core.config import get_settings
from src.core.exceptions import DomainError

settings = get_settings()
logger = logging.getLogger("scenecraft.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="SceneCraft API",
    version="0.1.0",
    description="Control-plane API for the SceneCraft agentic previs studio.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Minimal in-process rate limiting (sliding window per client IP) -------
# This is correct for local dev and a single Cloud Run instance only. Phase 6
# replaces it with a Redis-backed limiter shared across all instances — see
# docs/Phases/PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md SS4. Do not treat
# this as the permanent design.
_request_log: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next: Any) -> Any:
    client_key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _request_log[client_key]

    while window and now - window[0] > 60:
        window.popleft()

    if len(window) >= settings.rate_limit_requests_per_minute:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": {"code": "RATE_LIMITED", "message": "Too many requests, slow down."}},
        )

    window.append(now)
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
