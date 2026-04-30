"""Structured JSON logging configuration for mcp-siyuan."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from mcp_siyuan.observability.context import get_caller, get_request_id

# Reserved fields populated by the formatter from LogRecord.extra
_TOOL_FIELDS = (
    "tool_name",
    "args_size_bytes",
    "kernel_status",
    "latency_ms",
    "outcome",
)


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record.

    Required fields are always present; tool-call fields default to None when
    a record is emitted outside a traced tool invocation.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": get_request_id(),
            "caller": get_caller(),
            "message": record.getMessage(),
        }
        for field in _TOOL_FIELDS:
            payload[field] = getattr(record, field, None)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        try:
            return json.dumps(payload, default=str)
        except (TypeError, ValueError):
            payload["message"] = repr(record.msg)
            return json.dumps(payload, default=str)


def configure_logging(level: str | None = None) -> None:
    """Install the JSON formatter on the root logger.

    Idempotent: re-installs handlers if called more than once. Honors the
    SIYUAN_LOG_LEVEL setting unless an explicit level is passed.
    """
    from mcp_siyuan.config import settings

    target_level = (level or settings.siyuan_log_level or "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(target_level)
