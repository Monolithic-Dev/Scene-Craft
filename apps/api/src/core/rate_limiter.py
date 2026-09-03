"""Redis-backed distributed rate limiter — replaces the Phase 1 in-process
version (an in-memory deque per client, correct for local dev/a single
Cloud Run instance only — see docs/Phases/PHASE-01-FOUNDATIONS.md pitfall
#5 and the removed _request_log in main.py).

Algorithm: fixed-window counter (INCR + conditional EXPIRE on a
`ratelimit:<key>:<window_bucket>` key), not the sliding-window deque the
in-process version used. This is a deliberate simplification for real
atomicity across concurrent Cloud Run instances sharing one Redis: a plain
INCR is atomic on its own (no Lua/transaction needed), so "two instances
hitting the same user's bucket enforce the combined count once, not
doubled" holds trivially — see PHASE-06-OBSERVABILITY-SECURITY-
DEPLOYMENT.md SS4's required test. The tradeoff is the well-known fixed-
window edge case (up to ~2x the limit can pass across a window boundary),
accepted here because this is coarse abuse prevention, not a precision
SLA.

Keyed by authenticated user ID when a valid JWT is present (the phase
doc's explicit ask, "now that auth is fully wired"); falls back to client
IP for pre-auth endpoints (signup/login) where there is no user id yet.
"""
import time
from functools import lru_cache

import redis

from src.core.config import get_settings
from src.core.security import TokenError, decode_access_token


@lru_cache
def _default_client() -> redis.Redis:
    settings = get_settings()
    # protocol=2 (RESP2) pinned explicitly: redis-py 8.x's default RESP3
    # HELLO handshake was observed failing against a real local Redis 7
    # (redis:7-alpine via docker-compose) with "unknown command 'HELLO'" —
    # a genuine client/transport quirk hit during live verification, not a
    # server-side incompatibility (redis-cli's own HELLO against the same
    # server works fine). Only INCR/EXPIRE are used here, so RESP2 loses
    # nothing this module needs.
    return redis.Redis.from_url(settings.redis_url, decode_responses=False, protocol=2)


class RateLimiter:
    def __init__(self, client: redis.Redis | None = None) -> None:
        self._client = client or _default_client()

    def allow(self, key: str, *, limit: int, window_seconds: int = 60) -> bool:
        bucket = int(time.time() // window_seconds)
        redis_key = f"ratelimit:{key}:{bucket}"
        count = self._client.incr(redis_key)
        if count == 1:
            self._client.expire(redis_key, window_seconds)
        return count <= limit


def rate_limit_key(authorization_header: str | None, client_host: str | None) -> str:
    """user:<id> when the bearer token decodes successfully, else ip:<host>.
    Never raises — an expired/malformed/missing token just falls back to
    IP, exactly as an unauthenticated request would anyway (the route
    itself, not this key derivation, is what actually enforces auth).
    """
    if authorization_header and authorization_header.lower().startswith("bearer "):
        token = authorization_header[len("bearer ") :].strip()
        try:
            user_id = decode_access_token(token)
        except TokenError:
            pass
        else:
            return f"user:{user_id}"
    return f"ip:{client_host or 'unknown'}"
