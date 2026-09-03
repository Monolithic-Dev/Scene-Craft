"""Unit tests for the Redis-backed limiter itself (core/rate_limiter.py).
End-to-end 429 behavior through the actual middleware is covered by
test_jobs.py/test_projects.py's existing request flows indirectly; this
file is about the limiter's own correctness, especially the "shared across
instances" requirement from PHASE-06-OBSERVABILITY-SECURITY-DEPLOYMENT.md
SS4/SS9.
"""
import fakeredis

from src.core.rate_limiter import RateLimiter, rate_limit_key


def test_allows_requests_under_the_limit():
    limiter = RateLimiter(client=fakeredis.FakeRedis())
    for _ in range(5):
        assert limiter.allow("user:alice", limit=5) is True


def test_blocks_requests_over_the_limit():
    limiter = RateLimiter(client=fakeredis.FakeRedis())
    for _ in range(5):
        limiter.allow("user:alice", limit=5)
    assert limiter.allow("user:alice", limit=5) is False


def test_different_keys_have_independent_buckets():
    limiter = RateLimiter(client=fakeredis.FakeRedis())
    for _ in range(5):
        limiter.allow("user:alice", limit=5)
    assert limiter.allow("user:bob", limit=5) is True


def test_rate_limiter_shared_across_instances():
    """The phase doc's required test: simulate two "instances" (two
    RateLimiter objects, e.g. two Cloud Run replicas) hitting the same
    Redis for the same user — the combined count must be enforced once,
    not doubled. A shared fakeredis server (not two independent ones) is
    what actually simulates "two instances, one Redis".
    """
    shared_redis = fakeredis.FakeRedis()
    instance_a = RateLimiter(client=shared_redis)
    instance_b = RateLimiter(client=shared_redis)

    allowed = 0
    for i in range(10):
        instance = instance_a if i % 2 == 0 else instance_b
        if instance.allow("user:alice", limit=6):
            allowed += 1

    assert allowed == 6


def test_rate_limit_key_prefers_user_id_from_valid_bearer_token():
    from src.core.security import create_access_token

    token = create_access_token("user-42")
    key = rate_limit_key(f"Bearer {token}", "203.0.113.5")
    assert key == "user:user-42"


def test_rate_limit_key_falls_back_to_ip_when_no_token():
    assert rate_limit_key(None, "203.0.113.5") == "ip:203.0.113.5"


def test_rate_limit_key_falls_back_to_ip_when_token_invalid():
    key = rate_limit_key("Bearer not-a-real-token", "203.0.113.5")
    assert key == "ip:203.0.113.5"
