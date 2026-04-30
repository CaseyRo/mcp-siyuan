"""Tests for the observability layer (correlation IDs, JSON logging, diag buffer)."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from mcp_siyuan.observability import diag_buffer
from mcp_siyuan.observability.context import (
    get_request_id,
    set_caller,
    set_kernel_status,
    set_request_id,
)
from mcp_siyuan.observability.logging_setup import JsonFormatter
from mcp_siyuan.observability.tracing import traced_tool


@pytest.fixture(autouse=True)
def reset_diag_buffer():
    diag_buffer.reset_for_tests(maxlen=50)
    yield
    diag_buffer.reset_for_tests(maxlen=50)


@pytest.fixture
def reset_context():
    set_request_id(None)
    set_caller(None)
    set_kernel_status(None)
    yield
    set_request_id(None)
    set_caller(None)
    set_kernel_status(None)


@pytest.mark.asyncio
async def test_traced_tool_assigns_request_id(reset_context):
    seen: list[str | None] = []

    @traced_tool
    async def echo(value: str) -> str:
        seen.append(get_request_id())
        return value

    result = await echo("hello")
    assert result == "hello"
    assert seen[0] is not None
    assert len(seen[0]) >= 32  # uuid4 length


@pytest.mark.asyncio
async def test_concurrent_invocations_have_distinct_ids():
    """asyncio.gather two slow tools — each must see its own request_id."""

    captured: list[str | None] = []

    @traced_tool
    async def slow_tool(label: str) -> str:
        await asyncio.sleep(0.01)
        captured.append((label, get_request_id()))
        await asyncio.sleep(0.01)
        return label

    await asyncio.gather(slow_tool("a"), slow_tool("b"))
    ids = [rid for _, rid in captured]
    assert len(set(ids)) == 2
    assert all(rid is not None for rid in ids)


@pytest.mark.asyncio
async def test_traced_tool_appends_to_diag_buffer(reset_context):
    @traced_tool
    async def noop() -> str:
        return "ok"

    await noop()
    snap = diag_buffer.snapshot()
    assert len(snap) == 1
    entry = snap[0]
    assert entry["tool_name"] == "siyuan_noop"
    assert entry["outcome"] == "success"
    assert entry["request_id"] is not None
    assert entry["latency_ms"] is not None


@pytest.mark.asyncio
async def test_traced_tool_records_error_outcome(reset_context):
    @traced_tool
    async def boom() -> None:
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError) as exc_info:
        await boom()
    # Request ID must be appended to the error message
    assert "request_id=" in str(exc_info.value)
    snap = diag_buffer.snapshot()
    assert snap[-1]["outcome"] == "error"


@pytest.mark.asyncio
async def test_traced_tool_records_validation_error(reset_context):
    """Pydantic ValidationError → outcome=validation_error, kernel_status=null."""
    from pydantic import BaseModel, ValidationError

    class Args(BaseModel):
        n: int

    @traced_tool
    async def takes_int(n: int) -> int:
        # Force a Pydantic ValidationError mid-call
        Args.model_validate({"n": "not-a-number"})
        return n

    with pytest.raises(ValidationError):
        await takes_int(5)
    entry = diag_buffer.snapshot()[-1]
    assert entry["outcome"] == "validation_error"
    assert entry["kernel_status"] is None


def test_json_formatter_emits_required_fields():
    fmt = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.tool_name = "siyuan_create_document"
    record.args_size_bytes = 42
    record.kernel_status = "0"
    record.latency_ms = 17
    record.outcome = "success"

    out = fmt.format(record)
    parsed = json.loads(out)
    for field in (
        "ts",
        "level",
        "logger",
        "request_id",
        "caller",
        "message",
        "tool_name",
        "args_size_bytes",
        "kernel_status",
        "latency_ms",
        "outcome",
    ):
        assert field in parsed, f"missing {field} in {parsed}"
    assert parsed["tool_name"] == "siyuan_create_document"
    assert parsed["outcome"] == "success"


def test_json_formatter_handles_unserializable():
    fmt = JsonFormatter()

    class Weird:
        def __repr__(self):
            return "<Weird>"

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=Weird(),
        args=(),
        exc_info=None,
    )
    out = fmt.format(record)
    parsed = json.loads(out)
    assert "message" in parsed


def test_diag_buffer_bounded():
    diag_buffer.reset_for_tests(maxlen=3)
    for i in range(10):
        diag_buffer.append({"i": i})
    snap = diag_buffer.snapshot()
    assert len(snap) == 3
    assert [e["i"] for e in snap] == [7, 8, 9]


@pytest.mark.asyncio
async def test_traced_tool_includes_caller_when_set(reset_context):
    set_caller("bearer")

    @traced_tool
    async def t() -> str:
        return "ok"

    await t()
    entry = diag_buffer.snapshot()[-1]
    assert entry["caller"] == "bearer"
