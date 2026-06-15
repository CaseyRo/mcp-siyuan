"""@traced_tool decorator: correlation ID, structured logging, diag buffer."""

from __future__ import annotations

import functools
import inspect
import json
import logging
import time
from typing import Any, Awaitable, Callable

from pydantic import ValidationError

from mcp_siyuan.observability import diag_buffer
from mcp_siyuan.observability.context import (
    get_caller,
    get_kernel_status,
    new_request_id,
    set_kernel_status,
    set_request_id,
)

logger = logging.getLogger(__name__)


def _safe_args_size(args: tuple[Any, ...], kwargs: dict[str, Any]) -> int | None:
    try:
        blob = {"args": list(args), "kwargs": kwargs}
        return len(json.dumps(blob, default=str).encode("utf-8"))
    except Exception:
        return None


def _outcome_for(exc: BaseException | None) -> str:
    if exc is None:
        return "success"
    if isinstance(exc, ValidationError):
        return "validation_error"
    return "error"


def traced_tool(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Wrap a tool coroutine with correlation ID, log records, and diag append.

    Preserves the wrapped function's signature so FastMCP can introspect it
    for the tool schema.
    """

    if not inspect.iscoroutinefunction(func):
        raise TypeError(f"traced_tool requires a coroutine function, got {func!r}")

    tool_name = f"siyuan_{func.__name__}"

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        request_id = new_request_id()
        set_request_id(request_id)
        set_kernel_status(None)
        args_size = _safe_args_size(args, kwargs)

        logger.info(
            "tool.start",
            extra={
                "tool_name": tool_name,
                "args_size_bytes": args_size,
                "outcome": None,
                "kernel_status": None,
                "latency_ms": None,
            },
        )

        start = time.perf_counter()
        exc: BaseException | None = None
        try:
            return await func(*args, **kwargs)
        except BaseException as raised:
            exc = raised
            # Append request_id to the exception message so MCP clients see it
            # in the surfaced error payload. Original args preserved.
            # CDI-1093: when the underlying SiYuanError is flagged retryable
            # (transient 5xx / transport fault), also surface a `[retryable]`
            # marker so callers — including write tools, where we cannot return
            # a {retryable: true} envelope without breaking the raise-based
            # contract — know an identical retry is safe.
            retryable = bool(getattr(raised, "retryable", False))
            existing = list(getattr(raised, "args", ()))
            tail = f"[request_id={request_id}]"
            if retryable:
                tail = f"[retryable] {tail}"
            if existing and isinstance(existing[0], str) and "[request_id=" not in existing[0]:
                existing[0] = f"{existing[0]} {tail}"
                raised.args = tuple(existing)
            elif not existing:
                raised.args = (tail,)
            raise
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            outcome = _outcome_for(exc)
            kernel_status = get_kernel_status()
            record_extra = {
                "tool_name": tool_name,
                "args_size_bytes": args_size,
                "kernel_status": kernel_status,
                "latency_ms": latency_ms,
                "outcome": outcome,
            }
            if exc is None:
                logger.info("tool.end", extra=record_extra)
            else:
                logger.error("tool.end %s", exc, extra=record_extra)
            diag_buffer.append(
                {
                    "ts": time.time(),
                    "request_id": request_id,
                    "caller": get_caller(),
                    **record_extra,
                    "error": None if exc is None else f"{type(exc).__name__}: {exc}",
                }
            )

    return wrapper
