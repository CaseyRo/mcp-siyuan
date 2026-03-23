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
    from mcp_siyuan.tools.read import siyuan_list_notebooks

    mock_sy.call.return_value = {
        "notebooks": [
            {"id": "nb1", "name": "Work", "icon": "1f4bc", "sort": 0, "closed": False},
            {"id": "nb2", "name": "Personal", "icon": "1f3e0", "sort": 1, "closed": True},
        ]
    }
    result = await siyuan_list_notebooks()
    assert len(result) == 2
    assert result[0]["name"] == "Work"
    assert result[1]["closed"] is True
    mock_sy.call.assert_called_once_with("/api/notebook/lsNotebooks")


@pytest.mark.asyncio
async def test_sql_query(mock_sy):
    """sql_query returns rows from SiYuan SQL endpoint."""
    from mcp_siyuan.tools.read import siyuan_sql_query

    mock_sy.call.return_value = [
        {"id": "b1", "content": "TODO: fix tests"},
        {"id": "b2", "content": "TODO: deploy"},
    ]
    result = await siyuan_sql_query(stmt="SELECT id, content FROM blocks LIMIT 2")
    assert len(result) == 2
    assert result[0]["content"] == "TODO: fix tests"


@pytest.mark.asyncio
async def test_sql_query_empty(mock_sy):
    """sql_query returns empty list when no results."""
    from mcp_siyuan.tools.read import siyuan_sql_query

    mock_sy.call.return_value = []
    result = await siyuan_sql_query(stmt="SELECT * FROM blocks WHERE 1=0 LIMIT 10")
    assert result == []


@pytest.mark.asyncio
async def test_sql_query_rejects_non_select(mock_sy):
    """sql_query rejects non-SELECT statements."""
    from mcp_siyuan.tools.read import siyuan_sql_query

    with pytest.raises(ValueError, match="Only SELECT"):
        await siyuan_sql_query(stmt="DROP TABLE blocks")
    mock_sy.call.assert_not_called()


@pytest.mark.asyncio
async def test_sql_query_rejects_delete(mock_sy):
    """sql_query rejects DELETE statements."""
    from mcp_siyuan.tools.read import siyuan_sql_query

    with pytest.raises(ValueError, match="Only SELECT"):
        await siyuan_sql_query(stmt="DELETE FROM blocks WHERE id='b1'")


@pytest.mark.asyncio
async def test_sql_query_rejects_insert(mock_sy):
    """sql_query rejects INSERT statements."""
    from mcp_siyuan.tools.read import siyuan_sql_query

    with pytest.raises(ValueError, match="Only SELECT"):
        await siyuan_sql_query(stmt="INSERT INTO blocks VALUES ('x')")


@pytest.mark.asyncio
async def test_sql_query_auto_limit(mock_sy):
    """sql_query appends LIMIT when none provided."""
    from mcp_siyuan.tools.read import siyuan_sql_query

    mock_sy.call.return_value = []
    await siyuan_sql_query(stmt="SELECT * FROM blocks")
    call_kwargs = mock_sy.call.call_args
    assert "LIMIT 200" in call_kwargs.kwargs["stmt"]


@pytest.mark.asyncio
async def test_sql_query_preserves_existing_limit(mock_sy):
    """sql_query does not override an existing LIMIT."""
    from mcp_siyuan.tools.read import siyuan_sql_query

    mock_sy.call.return_value = []
    await siyuan_sql_query(stmt="SELECT * FROM blocks LIMIT 5")
    call_kwargs = mock_sy.call.call_args
    assert "LIMIT 200" not in call_kwargs.kwargs["stmt"]
    assert "LIMIT 5" in call_kwargs.kwargs["stmt"]


@pytest.mark.asyncio
async def test_get_document(mock_sy):
    """get_document returns markdown content."""
    from mcp_siyuan.tools.read import siyuan_get_document

    mock_sy.call.return_value = {"content": "# Hello\n\nWorld"}
    result = await siyuan_get_document(id="doc1")
    assert result == "# Hello\n\nWorld"


@pytest.mark.asyncio
async def test_get_document_truncation(mock_sy):
    """get_document truncates long content with correct message."""
    from mcp_siyuan.tools.read import siyuan_get_document

    mock_sy.call.return_value = {"content": "x" * 200}
    result = await siyuan_get_document(id="doc1", max_length=100)
    assert result.startswith("x" * 100)
    assert "truncated at 100 chars" in result


@pytest.mark.asyncio
async def test_search(mock_sy):
    """search returns formatted results."""
    from mcp_siyuan.tools.read import siyuan_search

    mock_sy.call.return_value = {
        "blocks": [
            {"id": "b1", "content": "meeting notes", "rootID": "r1", "box": "nb1", "hPath": "/notes"},
        ]
    }
    result = await siyuan_search(query="meeting")
    assert len(result) == 1
    assert result[0]["id"] == "b1"
    assert result[0]["hpath"] == "/notes"


@pytest.mark.asyncio
async def test_search_empty(mock_sy):
    """search returns empty list when no matches."""
    from mcp_siyuan.tools.read import siyuan_search

    mock_sy.call.return_value = {"blocks": []}
    result = await siyuan_search(query="nonexistent")
    assert result == []


@pytest.mark.asyncio
async def test_get_block(mock_sy):
    """get_block returns shaped block data with only essential fields."""
    from mcp_siyuan.tools.read import siyuan_get_block

    mock_sy.call.return_value = {
        "id": "b1", "type": "p", "content": "hello",
        "parentID": "doc1", "rootID": "r1", "box": "nb1",
        "hPath": "/notes", "updated": "20260320",
        "internalField": "should be dropped",
    }
    result = await siyuan_get_block(id="b1")
    assert result["type"] == "p"
    assert result["parent_id"] == "doc1"
    assert result["root_id"] == "r1"
    assert result["hpath"] == "/notes"
    assert "internalField" not in result


@pytest.mark.asyncio
async def test_get_block_not_found(mock_sy):
    """get_block returns error dict when block doesn't exist."""
    from mcp_siyuan.tools.read import siyuan_get_block

    mock_sy.call.return_value = None
    result = await siyuan_get_block(id="nonexistent")
    assert "error" in result


@pytest.mark.asyncio
async def test_get_block_attrs(mock_sy):
    """get_block_attrs returns attribute dict."""
    from mcp_siyuan.tools.read import siyuan_get_block_attrs

    mock_sy.call.return_value = {
        "id": "b1",
        "type": "doc",
        "custom-priority": "high",
    }
    result = await siyuan_get_block_attrs(id="b1")
    assert result["custom-priority"] == "high"
