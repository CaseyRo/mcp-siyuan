"""In-memory ring buffer of recent tool-call records for /health?diag=1."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any

_lock = threading.Lock()
_buffer: deque[dict[str, Any]] | None = None


def _get_buffer() -> deque[dict[str, Any]]:
    global _buffer
    if _buffer is None:
        from mcp_siyuan.config import settings

        _buffer = deque(maxlen=max(1, settings.siyuan_diag_buffer_size))
    return _buffer


def append(record: dict[str, Any]) -> None:
    with _lock:
        _get_buffer().append(record)


def snapshot() -> list[dict[str, Any]]:
    with _lock:
        return list(_get_buffer())


def reset_for_tests(maxlen: int | None = None) -> None:
    """Reset the buffer; tests use this to avoid cross-test contamination."""
    global _buffer
    with _lock:
        _buffer = deque(maxlen=maxlen if maxlen is not None else 50)
