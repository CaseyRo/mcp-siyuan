"""Shelf-item refinements (feat/shelf-items):

1. Tool tags on reads/writes/destructive ops.
2. Defensive ``ctx.elicit`` confirmation before delete_doc / delete_block /
   remove_notebook — must degrade gracefully when elicitation is unsupported.
3. ``siyuan://doc/{doc_id}/outline`` resource template reusing
   ``get_document_outline`` (pure read, error-path-safe).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fake elicitation Context helpers
# ---------------------------------------------------------------------------


class _Result:
    """Minimal stand-in for an Accepted/Declined/Cancelled elicitation result."""

    def __init__(self, action: str, data=None):
        self.action = action
        self.data = data


class _AcceptCtx:
    """Context whose elicit() always accepts (optionally with a bool answer)."""

    def __init__(self, data=True):
        self._data = data
        self.calls: list[str] = []

    async def elicit(self, message: str, response_type=None, **kw):
        self.calls.append(message)
        return _Result("accept", self._data)


class _DeclineCtx:
    def __init__(self):
        self.calls: list[str] = []

    async def elicit(self, message: str, response_type=None, **kw):
        self.calls.append(message)
        return _Result("decline")


class _CancelCtx:
    def __init__(self):
        self.calls: list[str] = []

    async def elicit(self, message: str, response_type=None, **kw):
        self.calls.append(message)
        return _Result("cancel")


class _UnsupportedCtx:
    """Context whose elicit() raises — i.e. the client can't elicit."""

    def __init__(self):
        self.calls: list[str] = []

    async def elicit(self, message: str, response_type=None, **kw):
        self.calls.append(message)
        raise RuntimeError("Client does not support elicitation")


@pytest.fixture
def mock_write_sy():
    with patch("mcp_siyuan.tools.write.sy") as mock:
        mock.call = AsyncMock()
        yield mock


@pytest.fixture(autouse=True)
def _reset_idempotency():
    from mcp_siyuan.idempotency import cache as idempotency_cache

    idempotency_cache.reset_for_tests(ttl_seconds=300)
    yield


# ---------------------------------------------------------------------------
# _confirm_destructive — the shared defensive gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_destructive_no_ctx_proceeds():
    from mcp_siyuan.tools.write import _confirm_destructive

    assert await _confirm_destructive(None, "msg") is True


@pytest.mark.asyncio
async def test_confirm_destructive_accept_proceeds():
    from mcp_siyuan.tools.write import _confirm_destructive

    ctx = _AcceptCtx(data=True)
    assert await _confirm_destructive(ctx, "msg") is True
    assert ctx.calls == ["msg"]


@pytest.mark.asyncio
async def test_confirm_destructive_accept_false_aborts():
    """An explicit ``False`` answer means 'do not delete'."""
    from mcp_siyuan.tools.write import _confirm_destructive

    assert await _confirm_destructive(_AcceptCtx(data=False), "msg") is False


@pytest.mark.asyncio
async def test_confirm_destructive_decline_aborts():
    from mcp_siyuan.tools.write import _confirm_destructive

    assert await _confirm_destructive(_DeclineCtx(), "msg") is False


@pytest.mark.asyncio
async def test_confirm_destructive_cancel_aborts():
    from mcp_siyuan.tools.write import _confirm_destructive

    assert await _confirm_destructive(_CancelCtx(), "msg") is False


@pytest.mark.asyncio
async def test_confirm_destructive_unsupported_proceeds():
    """Graceful degradation: elicit raising (unsupported) must PROCEED."""
    from mcp_siyuan.tools.write import _confirm_destructive

    ctx = _UnsupportedCtx()
    assert await _confirm_destructive(ctx, "msg") is True
    assert ctx.calls == ["msg"]  # it tried, then degraded


# ---------------------------------------------------------------------------
# delete_block
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_block_no_ctx_still_deletes(mock_write_sy):
    """Default path (no elicitation) is unchanged — kernel delete fires."""
    from mcp_siyuan.tools.write import delete_block

    mock_write_sy.call.return_value = [{"doOperations": [{"action": "delete"}]}]
    result = await delete_block(id="b1")
    assert result.ok is True
    mock_write_sy.call.assert_called_once_with("/api/block/deleteBlock", id="b1")


@pytest.mark.asyncio
async def test_delete_block_accept_deletes(mock_write_sy):
    from mcp_siyuan.tools.write import delete_block

    mock_write_sy.call.return_value = [{"doOperations": [{"action": "delete"}]}]
    ctx = _AcceptCtx()
    result = await delete_block(id="b1", ctx=ctx)
    assert result.ok is True
    assert ctx.calls  # confirmation was requested
    mock_write_sy.call.assert_called_once_with("/api/block/deleteBlock", id="b1")


@pytest.mark.asyncio
async def test_delete_block_decline_aborts_without_kernel_call(mock_write_sy):
    from mcp_siyuan.tools.write import delete_block

    result = await delete_block(id="b1", ctx=_DeclineCtx())
    assert result.ok is False
    assert result.model_dump().get("cancelled") is True
    assert "cancelled" in (result.error or "")
    mock_write_sy.call.assert_not_called()  # nothing deleted


@pytest.mark.asyncio
async def test_delete_block_unsupported_still_deletes(mock_write_sy):
    """Client can't elicit → proceed with the delete (destructiveHint warns)."""
    from mcp_siyuan.tools.write import delete_block

    mock_write_sy.call.return_value = [{"doOperations": [{"action": "delete"}]}]
    result = await delete_block(id="b1", ctx=_UnsupportedCtx())
    assert result.ok is True
    mock_write_sy.call.assert_called_once_with("/api/block/deleteBlock", id="b1")


# ---------------------------------------------------------------------------
# remove_notebook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_notebook_no_ctx_still_removes(mock_write_sy):
    from mcp_siyuan.tools.write import remove_notebook

    mock_write_sy.call.return_value = None
    result = await remove_notebook(notebook="nb1")
    assert result.ok is True
    mock_write_sy.call.assert_called_once_with(
        "/api/notebook/removeNotebook", notebook="nb1"
    )


@pytest.mark.asyncio
async def test_remove_notebook_cancel_aborts(mock_write_sy):
    from mcp_siyuan.tools.write import remove_notebook

    result = await remove_notebook(notebook="nb1", ctx=_CancelCtx())
    assert result.ok is False
    assert result.model_dump().get("cancelled") is True
    mock_write_sy.call.assert_not_called()


@pytest.mark.asyncio
async def test_remove_notebook_unsupported_still_removes(mock_write_sy):
    from mcp_siyuan.tools.write import remove_notebook

    mock_write_sy.call.return_value = None
    result = await remove_notebook(notebook="nb1", ctx=_UnsupportedCtx())
    assert result.ok is True
    mock_write_sy.call.assert_called_once()


# ---------------------------------------------------------------------------
# delete_doc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_doc_decline_aborts_before_lookup(mock_write_sy):
    """Decline must short-circuit BEFORE any kernel lookup/remove call."""
    from mcp_siyuan.tools.write import delete_doc

    result = await delete_doc(id="doc1", ctx=_DeclineCtx())
    assert result.ok is False
    assert result.deleted_id == "doc1"
    assert result.model_dump().get("cancelled") is True
    mock_write_sy.call.assert_not_called()


@pytest.mark.asyncio
async def test_delete_doc_accept_removes(mock_write_sy):
    from mcp_siyuan.tools.write import delete_doc

    responses = [
        {"id": "doc1", "type": "d", "rootID": "doc1"},  # getBlockInfo
        [{"id": "doc1", "type": "d", "box": "nb1", "path": "/foo.sy"}],  # SQL lookup
        None,  # removeDocByID
    ]

    async def mock_call(endpoint, **kwargs):
        return responses.pop(0)

    mock_write_sy.call = mock_call
    result = await delete_doc(id="doc1", ctx=_AcceptCtx())
    assert result.ok is True
    assert result.deleted_id == "doc1"
    assert result.already_absent is False


@pytest.mark.asyncio
async def test_delete_doc_unsupported_removes(mock_write_sy):
    """Elicitation unsupported → proceed with removal."""
    from mcp_siyuan.tools.write import delete_doc

    calls: list[str] = []
    responses = [
        {"id": "doc1", "type": "d", "rootID": "doc1"},
        [{"id": "doc1", "type": "d", "box": "nb1", "path": "/foo.sy"}],
        None,
    ]

    async def mock_call(endpoint, **kwargs):
        calls.append(endpoint)
        return responses.pop(0)

    mock_write_sy.call = mock_call
    result = await delete_doc(id="doc1", ctx=_UnsupportedCtx())
    assert result.ok is True
    assert "/api/filetree/removeDocByID" in calls


# ---------------------------------------------------------------------------
# Tags (Task 1) — assert the destructive trio + a read + a write are tagged.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_tags_present():
    from mcp_siyuan import server

    tools = await server.mcp.list_tools()
    by_name = {t.name: set(t.tags or []) for t in tools}

    # Destructive trio: {"write", "destructive"} (other tags may also be present).
    for name in ("delete_doc", "delete_block", "remove_notebook"):
        assert {"write", "destructive"} <= by_name[name], (name, by_name[name])

    # A pure read carries "read" and NOT "write"/"destructive".
    assert "read" in by_name["get_document"]
    assert "write" not in by_name["get_document"]
    assert "destructive" not in by_name["get_document"]

    # A plain write carries "write" and NOT "destructive".
    assert "write" in by_name["create_document"]
    assert "destructive" not in by_name["create_document"]


@pytest.mark.asyncio
async def test_every_write_tool_tagged_write():
    """All registered tools carry at least one of read/write tags."""
    from mcp_siyuan import server

    tools = await server.mcp.list_tools()
    for t in tools:
        tags = set(t.tags or [])
        assert ("read" in tags) or ("write" in tags), (t.name, tags)
        if "destructive" in tags:
            assert "write" in tags, (t.name, tags)


# ---------------------------------------------------------------------------
# Resource template (Task 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_outline_resource_template_registered():
    from mcp_siyuan import server

    tmpls = await server.mcp.list_resource_templates()
    uris = {t.uri_template for t in tmpls}
    assert "siyuan://doc/{doc_id}/outline" in uris


@pytest.mark.asyncio
async def test_outline_resource_success_reuses_tool():
    """The resource returns get_document_outline's rows as a JSON array."""
    from mcp_siyuan import server

    with patch("mcp_siyuan.tools.smart.sy") as msy:
        msy.call = AsyncMock(
            return_value=[
                {"id": "h1", "content": "Intro", "level": "h1", "sort": 0},
                {"id": "h2", "content": "Body", "level": "h2", "sort": 10},
            ]
        )
        body = await server.doc_outline_resource("doc1")

    rows = json.loads(body)
    assert [r["content"] for r in rows] == ["Intro", "Body"]
    assert rows[0]["level"] == "h1"
    # The SQL the underlying tool fired must be a heading-only read.
    stmt = msy.call.call_args.kwargs["stmt"]
    assert "type = 'h'" in stmt


@pytest.mark.asyncio
async def test_outline_resource_error_path_safe():
    """An unsafe doc_id is caught and returned as a single error row, not raised."""
    from mcp_siyuan import server

    body = await server.doc_outline_resource("bad'; DROP TABLE blocks; --")
    rows = json.loads(body)
    assert len(rows) == 1
    assert rows[0]["error"]
    assert "Unsafe characters" in rows[0]["error"]


@pytest.mark.asyncio
async def test_outline_resource_read_end_to_end():
    """Reading via the MCP resource path returns JSON without raising."""
    from mcp_siyuan import server

    with patch("mcp_siyuan.tools.smart.sy") as msy:
        msy.call = AsyncMock(
            return_value=[{"id": "h1", "content": "Intro", "level": "h1", "sort": 0}]
        )
        rr = await server.mcp.read_resource("siyuan://doc/doc1/outline")

    block = rr.contents[0]
    text = getattr(block, "text", None) or getattr(block, "content", None)
    rows = json.loads(text)
    assert rows[0]["id"] == "h1"
