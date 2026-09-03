"""Structured (JSON) logging setup — replaces the bare logging.basicConfig
call that shipped in Phases 1-5. Every existing `logger.warning(msg,
extra={...})` call site across the codebase keeps working unchanged; this
only changes the emitted line's *shape* from plain text to one JSON object
per line, so a real log sink (Cloud Logging, or a `grep`/`jq` pass during
the Phase 6 security review's "no secret values appear in logs" check) can
actually query the structured fields instead of pattern-matching text.
"""
import json
import logging
from datetime import UTC, datetime
from typing import Any

_RESERVED_LOG_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Fields passed via extra={...} — everything on the record that
        # isn't one of Python's own built-in LogRecord attributes.
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_ATTRS:
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
