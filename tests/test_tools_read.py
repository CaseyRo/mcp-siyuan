"""Tests for Tier 1 read/query tools."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_sy():
    with patch("mcp_siyuan.tools.read.sy") as mock:
        mock.call = AsyncMock()
        yield mock


@pytest.mark.asyncio
async def test_list_notebooks(mock_sy):
    """list_notebooks returns parsed notebook list."""
    from mcp_siyuan.tools.read import list_notebooks

    mock_sy.call.return_value = {
        "notebooks": [
            {"id": "nb1", "name": "Work", "icon": "1f4bc", "sort": 0, "closed": False},
            {"id": "nb2", "name": "Personal", "icon": "1f3e0", "sort": 1, "closed": True},
        ]
    }
    result = await list_notebooks()
    assert len(result) == 2
    assert result[0].name == "Work"
    assert result[1].closed is True
    mock_sy.call.assert_called_once_with("/api/notebook/lsNotebooks")


@pytest.mark.asyncio
async def test_sql_query(mock_sy):
    """sql_query returns rows from SiYuan SQL endpoint."""
    from mcp_siyuan.tools.read import sql_query

    mock_sy.call.return_value = [
        {"id": "b1", "content": "TODO: fix tests"},
        {"id": "b2", "content": "TODO: deploy"},
    ]
    result = await sql_query(stmt="SELECT id, content FROM blocks LIMIT 2")
    assert len(result) == 2
    assert result[0].content == "TODO: fix tests"


@pytest.mark.asyncio
async def test_sql_query_empty(mock_sy):
    """sql_query returns empty list when no results."""
    from mcp_siyuan.tools.read import sql_query

    mock_sy.call.return_value = []
    result = await sql_query(stmt="SELECT * FROM blocks WHERE 1=0 LIMIT 10")
    assert result == []


@pytest.mark.asyncio
async def test_sql_query_rejects_non_select(mock_sy):
    """sql_query rejects non-SELECT statements."""
    from mcp_siyuan.tools.read import sql_query

    with pytest.raises(ValueError, match="Only SELECT"):
        await sql_query(stmt="DROP TABLE blocks")
    mock_sy.call.assert_not_called()


@pytest.mark.asyncio
async def test_sql_query_rejects_delete(mock_sy):
    """sql_query rejects DELETE statements."""
    from mcp_siyuan.tools.read import sql_query

    with pytest.raises(ValueError, match="Only SELECT"):
        await sql_query(stmt="DELETE FROM blocks WHERE id='b1'")


@pytest.mark.asyncio
async def test_sql_query_rejects_insert(mock_sy):
    """sql_query rejects INSERT statements."""
    from mcp_siyuan.tools.read import sql_query

    with pytest.raises(ValueError, match="Only SELECT"):
        await sql_query(stmt="INSERT INTO blocks VALUES ('x')")


@pytest.mark.asyncio
async def test_sql_query_auto_limit(mock_sy):
    """sql_query appends LIMIT when none provided."""
    from mcp_siyuan.tools.read import sql_query

    mock_sy.call.return_value = []
    await sql_query(stmt="SELECT * FROM blocks")
    call_kwargs = mock_sy.call.call_args
    assert "LIMIT 200" in call_kwargs.kwargs["stmt"]


@pytest.mark.asyncio
async def test_sql_query_preserves_existing_limit(mock_sy):
    """sql_query does not override an existing LIMIT."""
    from mcp_siyuan.tools.read import sql_query

    mock_sy.call.return_value = []
    await sql_query(stmt="SELECT * FROM blocks LIMIT 5")
    call_kwargs = mock_sy.call.call_args
    assert "LIMIT 200" not in call_kwargs.kwargs["stmt"]
    assert "LIMIT 5" in call_kwargs.kwargs["stmt"]


@pytest.mark.asyncio
async def test_get_document(mock_sy):
    """get_document returns markdown content."""
    from mcp_siyuan.tools.read import get_document

    mock_sy.call.return_value = {"content": "# Hello\n\nWorld"}
    result = await get_document(id="doc1")
    assert result == "# Hello\n\nWorld"


@pytest.mark.asyncio
async def test_get_document_truncation(mock_sy):
    """get_document truncates long content with correct message."""
    from mcp_siyuan.tools.read import get_document

    mock_sy.call.return_value = {"content": "x" * 200}
    result = await get_document(id="doc1", max_length=100)
    assert result.startswith("x" * 100)
    assert "truncated at 100 chars" in result


@pytest.mark.asyncio
async def test_search(mock_sy):
    """search returns formatted results."""
    from mcp_siyuan.tools.read import search

    mock_sy.call.return_value = {
        "blocks": [
            {"id": "b1", "content": "meeting notes", "rootID": "r1", "box": "nb1", "hPath": "/notes"},
        ]
    }
    result = await search(query="meeting")
    assert len(result) == 1
    assert result[0].id == "b1"
    assert result[0].hpath == "/notes"


@pytest.mark.asyncio
async def test_search_empty(mock_sy):
    """search returns empty list when no matches."""
    from mcp_siyuan.tools.read import search

    mock_sy.call.return_value = {"blocks": []}
    result = await search(query="nonexistent")
    assert result == []


def _block_mock(sql_rows, kramdown, info=None):
    """Kernel stub. Real getBlockInfo returns only root/box/path metadata —
    no type, content or parent (CDI-1550) — so the mock does the same."""

    async def mock_call(endpoint, **kwargs):
        if endpoint == "/api/query/sql":
            return sql_rows
        if endpoint == "/api/block/getBlockKramdown":
            return {"id": kwargs["id"], "kramdown": kramdown}
        if endpoint == "/api/block/getBlockInfo":
            return info or {"rootID": "r1", "box": "nb1", "path": "/r1.sy", "rootTitle": "T"}
        raise AssertionError(endpoint)

    return mock_call


@pytest.mark.asyncio
async def test_get_block(mock_sy):
    """get_block returns type, content, markdown, parent and root (CDI-1550)."""
    from mcp_siyuan.tools.read import get_block

    mock_sy.call = _block_mock(
        [{"id": "b1", "type": "p", "content": "hello", "parent_id": "doc1",
          "root_id": "r1", "box": "nb1", "hpath": "/notes", "updated": "20260320",
          "markdown": "hello"}],
        'hello **now**\n{: id="b1" updated="20260321"}',
    )
    result = await get_block(id="b1")
    assert result.error is None
    assert result.type == "p"
    assert result.content == "hello"
    assert result.markdown == "hello **now**"  # kernel wins over the index
    assert result.parent_id == "doc1"
    assert result.root_id == "r1"
    assert result.hpath == "/notes"


@pytest.mark.asyncio
async def test_get_block_not_indexed_yet(mock_sy):
    """Fresh block missing from the SQL index still returns kernel content."""
    from mcp_siyuan.tools.read import get_block

    mock_sy.call = _block_mock([], 'fresh text\n{: id="b2"}')
    result = await get_block(id="b2")
    assert result.id == "b2"
    assert result.markdown == "fresh text"
    assert result.content == "fresh text"
    assert result.root_id == "r1"
    assert result.box == "nb1"


@pytest.mark.asyncio
async def test_get_block_not_found(mock_sy):
    """get_block returns error when neither index nor kernel know the block."""
    from mcp_siyuan.tools.read import get_block

    mock_sy.call = _block_mock([], "")
    result = await get_block(id="nonexistent")
    assert result.error is not None
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_get_block_attrs(mock_sy):
    """get_block_attrs returns attribute dict."""
    from mcp_siyuan.tools.read import get_block_attrs

    mock_sy.call.return_value = {
        "id": "b1",
        "type": "doc",
        "custom-priority": "high",
    }
    result = await get_block_attrs(id="b1")
    assert result["custom-priority"] == "high"
