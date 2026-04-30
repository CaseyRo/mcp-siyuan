"""Per-request correlation ID stored in an async-safe ContextVar."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("mcp_siyuan_request_id", default=None)
_caller: ContextVar[str | None] = ContextVar("mcp_siyuan_caller", default=None)
_kernel_status: ContextVar[str | None] = ContextVar(
    "mcp_siyuan_kernel_status", default=None
)


def new_request_id() -> str:
    return str(uuid.uuid4())


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()


def set_caller(value: str | None) -> None:
    _caller.set(value)


def get_caller() -> str | None:
    return _caller.get()


def set_kernel_status(value: str | None) -> None:
    _kernel_status.set(value)


def get_kernel_status() -> str | None:
    return _kernel_status.get()
