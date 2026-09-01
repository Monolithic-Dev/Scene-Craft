"""Password hashing and JWT issuance/verification.

Uses the `bcrypt` library directly rather than passlib's bcrypt wrapper —
passlib's version-detection shim is unmaintained and breaks against modern
bcrypt releases, so we avoid that indirection entirely in production code.
"""
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from src.core.config import get_settings

settings = get_settings()

_MAX_BCRYPT_BYTES = 72  # bcrypt silently ignores bytes beyond this; we reject up front instead.


def hash_password(plain_password: str) -> str:
    encoded = plain_password.encode("utf-8")
    if len(encoded) > _MAX_BCRYPT_BYTES:
        raise ValueError(f"Password must be at most {_MAX_BCRYPT_BYTES} bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


class TokenError(Exception):
    """Raised when a token is missing, expired, or invalid."""


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    encoded: str = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded


def decode_access_token(token: str) -> str:
    """Returns the subject (user id) encoded in a valid token, or raises TokenError."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise TokenError("Invalid or expired token") from exc

    subject = payload.get("sub")
    if subject is None:
        raise TokenError("Token missing subject claim")
    return str(subject)
