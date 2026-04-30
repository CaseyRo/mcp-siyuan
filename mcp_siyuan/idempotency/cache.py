"""In-process TTL cache shared by all write tools."""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

from cachetools import TTLCache

logger = logging.getLogger(__name__)

_KEY_RE = re.compile(r"^[A-Za-z0-9_\-:.]+$")
_KEY_MAX_LEN = 128

_lock = threading.Lock()
_cache: TTLCache | None = None
MISS = object()


def _get_cache() -> TTLCache:
    global _cache
    if _cache is None:
        from mcp_siyuan.config import settings

        _cache = TTLCache(
            maxsize=1024,
            ttl=max(1, settings.siyuan_idempotency_ttl_seconds),
        )
    return _cache


class InvalidIdempotencyKey(ValueError):
    """Raised when an idempotency_key fails validation."""


def validate_key(key: str) -> None:
    if not isinstance(key, str) or not key:
        raise InvalidIdempotencyKey("idempotency_key must be a non-empty string")
    if len(key) > _KEY_MAX_LEN:
        raise InvalidIdempotencyKey(
            f"idempotency_key longer than {_KEY_MAX_LEN} characters"
        )
    if not _KEY_RE.fullmatch(key):
        raise InvalidIdempotencyKey(
            "idempotency_key must match ^[A-Za-z0-9_\\-:.]+$"
        )


def get(tool_name: str, key: str) -> Any:
    """Return cached value for `(tool_name, key)` or `MISS` on miss."""
    with _lock:
        return _get_cache().get((tool_name, key), MISS)


def put(tool_name: str, key: str, value: Any) -> None:
    """Store a *successful* tool result. Failures must NOT be cached."""
    with _lock:
        _get_cache()[(tool_name, key)] = value


async def with_idempotency(
    tool_name: str,
    idempotency_key: str | None,
    call,
) -> Any:
    """Run `call()` with optional replay-cache semantics.

    `call` is a no-arg coroutine factory (`async def () -> Any`) that performs
    the actual kernel work. Cache hits short-circuit `call`. Cache misses run
    `call` and store on success. Exceptions propagate WITHOUT writing to cache.
    """
    if idempotency_key is None:
        return await call()
    validate_key(idempotency_key)
    cached = get(tool_name, idempotency_key)
    if cached is not MISS:
        logger.info(
            "idempotency.hit", extra={"tool_name": tool_name}
        )
        return cached
    logger.info("idempotency.miss", extra={"tool_name": tool_name})
    result = await call()
    put(tool_name, idempotency_key, result)
    return result


def reset_for_tests(ttl_seconds: int | None = None) -> None:
    """Reset the cache; tests use this to control TTL deterministically."""
    global _cache
    with _lock:
        _cache = TTLCache(
            maxsize=1024,
            ttl=ttl_seconds if ttl_seconds is not None else 300,
        )
