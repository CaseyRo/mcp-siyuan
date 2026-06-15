"""Tests for the write-tool idempotency cache and validation."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from mcp_siyuan.idempotency import cache as idempotency_cache
from mcp_siyuan.idempotency.cache import InvalidIdempotencyKey


@pytest.fixture(autouse=True)
def reset_cache():
    idempotency_cache.reset_for_tests(ttl_seconds=300)
    yield
    idempotency_cache.reset_for_tests(ttl_seconds=300)


@pytest.fixture
def mock_sy():
    with patch("mcp_siyuan.tools.write.sy") as mock:
        mock.call = AsyncMock()
        yield mock


@pytest.mark.asyncio
async def test_replay_within_ttl_returns_cached_value(mock_sy):
    from mcp_siyuan.tools.write import create_document

    mock_sy.call.return_value = "doc-id-1"
    first = await create_document(
        notebook="nb1", path="/x", markdown="# A", idempotency_key="K1"
    )
    second = await create_document(
        notebook="nb1", path="/x", markdown="# A", idempotency_key="K1"
    )
    assert first == "doc-id-1"
    assert second == "doc-id-1"
    assert mock_sy.call.call_count == 1


@pytest.mark.asyncio
async def test_replay_after_ttl_invokes_kernel_again(mock_sy):
    """Use a 1-second TTL and sleep briefly to force expiry."""
    idempotency_cache.reset_for_tests(ttl_seconds=1)
    from mcp_siyuan.tools.write import create_document

    mock_sy.call.return_value = "doc-id-2"
    await create_document(
        notebook="nb1", path="/x", markdown="# A", idempotency_key="K2"
    )
    time.sleep(1.05)
    await create_document(
        notebook="nb1", path="/x", markdown="# A", idempotency_key="K2"
    )
    assert mock_sy.call.call_count == 2


@pytest.mark.asyncio
async def test_kernel_error_does_not_cache(mock_sy):
    from mcp_siyuan.client import SiYuanError
    from mcp_siyuan.tools.write import create_document

    mock_sy.call.side_effect = [SiYuanError("nope", code=42), "doc-id-after"]

    with pytest.raises(SiYuanError):
        await create_document(
            notebook="nb1", path="/x", markdown="# A", idempotency_key="K3"
        )
    # Identical retry must hit the kernel again, not the cache
    result = await create_document(
        notebook="nb1", path="/x", markdown="# A", idempotency_key="K3"
    )
    assert result == "doc-id-after"
    assert mock_sy.call.call_count == 2


@pytest.mark.asyncio
async def test_exception_does_not_cache(mock_sy):
    from mcp_siyuan.tools.write import create_document

    mock_sy.call.side_effect = [RuntimeError("boom"), "doc-id-after"]

    with pytest.raises(RuntimeError):
        await create_document(
            notebook="nb1", path="/x", markdown="# A", idempotency_key="K4"
        )
    result = await create_document(
        notebook="nb1", path="/x", markdown="# A", idempotency_key="K4"
    )
    assert result == "doc-id-after"


@pytest.mark.asyncio
async def test_same_key_different_tools_no_collision(mock_sy):
    from mcp_siyuan.tools.write import append_block, create_document

    mock_sy.call.side_effect = ["doc-id-X", {"ok": True, "transactions": []}]
    a = await create_document(
        notebook="nb1", path="/x", markdown="", idempotency_key="SHARED"
    )
    b = await append_block(parent_id="b1", data="hi", idempotency_key="SHARED")
    assert a == "doc-id-X"
    # append_block now returns a typed WriteResult; the kernel dict is preserved.
    assert b.ok is True
    assert b.transactions == []
    assert mock_sy.call.call_count == 2


@pytest.mark.asyncio
async def test_rename_doc_replays_with_key(mock_sy):
    """rename_doc honours idempotency_key so retries don't re-apply (CDI-1093)."""
    from mcp_siyuan.tools.write import rename_doc

    mock_sy.call.return_value = {"ok": True}
    first = await rename_doc(id="d1", title="New Title", idempotency_key="RN1")
    second = await rename_doc(id="d1", title="New Title", idempotency_key="RN1")
    assert first.ok is True
    assert second.ok is True
    assert mock_sy.call.call_count == 1


@pytest.mark.asyncio
async def test_move_doc_replays_with_key(mock_sy):
    """move_doc honours idempotency_key so retries don't re-apply (CDI-1093)."""
    from mcp_siyuan.tools.write import move_doc

    mock_sy.call.return_value = {"ok": True}
    first = await move_doc(from_ids=["d1"], to_id="nb2", idempotency_key="MV1")
    second = await move_doc(from_ids=["d1"], to_id="nb2", idempotency_key="MV1")
    assert first.ok is True
    assert second.ok is True
    assert mock_sy.call.call_count == 1


@pytest.mark.asyncio
async def test_omitted_key_preserves_legacy_behavior(mock_sy):
    """No key → no cache lookup, no cache store, kernel called every time."""
    from mcp_siyuan.tools.write import create_document

    mock_sy.call.side_effect = ["a", "b"]
    r1 = await create_document(notebook="nb1", path="/x", markdown="")
    r2 = await create_document(notebook="nb1", path="/x", markdown="")
    assert r1 == "a"
    assert r2 == "b"
    assert mock_sy.call.call_count == 2


@pytest.mark.parametrize(
    "bad_key",
    [
        "",
        "a" * 129,
        "has space",
        "has!bang",
        "has\nnewline",
    ],
)
@pytest.mark.asyncio
async def test_invalid_key_rejected_before_kernel(mock_sy, bad_key):
    from mcp_siyuan.tools.write import create_document

    mock_sy.call.return_value = "should-not-be-called"
    with pytest.raises(InvalidIdempotencyKey):
        await create_document(
            notebook="nb1", path="/x", markdown="", idempotency_key=bad_key
        )
    mock_sy.call.assert_not_called()


@pytest.mark.parametrize(
    "good_key",
    [
        "K",
        "uuid-abc-123",
        "funkstrecke-2026-04-29:v1",
        "a" * 128,
        "dot.separated.key",
    ],
)
@pytest.mark.asyncio
async def test_valid_keys_accepted(mock_sy, good_key):
    from mcp_siyuan.tools.write import create_document

    mock_sy.call.return_value = "doc-id"
    result = await create_document(
        notebook="nb1", path="/x", markdown="", idempotency_key=good_key
    )
    assert result == "doc-id"
