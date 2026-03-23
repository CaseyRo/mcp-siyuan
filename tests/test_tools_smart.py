"""Tests for high-level smart tools."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_sy():
    with patch("mcp_siyuan.tools.smart.sy") as mock:
        mock.call = AsyncMock()
        yield mock


@pytest.mark.asyncio
async def test_get_recent_docs(mock_sy):
    """get_recent_docs returns recent documents."""
    from mcp_siyuan.tools.smart import siyuan_get_recent_docs

    mock_sy.call.return_value = [
        {"id": "d1", "title": "Meeting Notes", "box": "nb1", "hpath": "/notes", "updated": "20260320"},
        {"id": "d2", "title": "TODO List", "box": "nb1", "hpath": "/tasks", "updated": "20260319"},
    ]
    result = await siyuan_get_recent_docs(limit=5)
    assert len(result) == 2
    assert result[0]["title"] == "Meeting Notes"


@pytest.mark.asyncio
async def test_get_recent_docs_filtered_by_notebook(mock_sy):
    """get_recent_docs filters by notebook when provided."""
    from mcp_siyuan.tools.smart import siyuan_get_recent_docs

    mock_sy.call.return_value = []
    await siyuan_get_recent_docs(notebook="nb1")
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "nb1" in stmt


@pytest.mark.asyncio
async def test_find_tasks_open(mock_sy):
    """find_tasks returns open tasks with doc_title."""
    from mcp_siyuan.tools.smart import siyuan_find_tasks

    mock_sy.call.return_value = [
        {"id": "t1", "content": "Buy groceries", "box": "nb1", "hpath": "/daily/2026-03-20", "root_id": "r1", "updated": "20260320", "doc_title": "Daily Note"},
    ]
    result = await siyuan_find_tasks()
    assert len(result) == 1
    assert result[0]["content"] == "Buy groceries"
    assert result[0]["doc_title"] == "Daily Note"
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "'t'" in stmt  # unchecked subtype
    assert "doc_title" in stmt  # JOIN for doc title


@pytest.mark.asyncio
async def test_find_tasks_checked(mock_sy):
    """find_tasks can return completed tasks."""
    from mcp_siyuan.tools.smart import siyuan_find_tasks

    mock_sy.call.return_value = []
    await siyuan_find_tasks(checked=True)
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "'d'" in stmt  # checked subtype


@pytest.mark.asyncio
async def test_find_tasks_scoped_to_notebook(mock_sy):
    """find_tasks filters by notebook."""
    from mcp_siyuan.tools.smart import siyuan_find_tasks

    mock_sy.call.return_value = []
    await siyuan_find_tasks(notebook="nb1")
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "nb1" in stmt


@pytest.mark.asyncio
async def test_get_backlinks(mock_sy):
    """get_backlinks returns referencing blocks with doc_title."""
    from mcp_siyuan.tools.smart import siyuan_get_backlinks

    mock_sy.call.return_value = {
        "backlinks": [
            {
                "name": "Notes Document",
                "backlinks": [
                    {"id": "b1", "content": "See also [[doc]]", "type": "p", "hPath": "/notes", "box": "nb1"},
                    {"id": "b2", "content": "Related: [[doc]]", "type": "p", "hPath": "/research", "box": "nb1"},
                ]
            }
        ]
    }
    result = await siyuan_get_backlinks(id="doc1")
    assert len(result) == 2
    assert result[0]["content"] == "See also [[doc]]"
    assert result[0]["doc_title"] == "Notes Document"


@pytest.mark.asyncio
async def test_get_backlinks_empty(mock_sy):
    """get_backlinks returns empty list when no refs."""
    from mcp_siyuan.tools.smart import siyuan_get_backlinks

    mock_sy.call.return_value = {"backlinks": []}
    result = await siyuan_get_backlinks(id="orphan")
    assert result == []


@pytest.mark.asyncio
async def test_get_tags(mock_sy):
    """get_tags flattens nested tag tree."""
    from mcp_siyuan.tools.smart import siyuan_get_tags

    mock_sy.call.return_value = {
        "tags": [
            {"label": "cars", "count": 5, "tags": [
                {"label": "porsche", "count": 3, "tags": []},
            ]},
            {"label": "wishlist", "count": 2, "tags": []},
        ]
    }
    result = await siyuan_get_tags()
    assert len(result) == 3
    assert {"tag": "cars", "count": 5} in result
    assert {"tag": "cars/porsche", "count": 3} in result
    assert {"tag": "wishlist", "count": 2} in result


@pytest.mark.asyncio
async def test_get_tags_empty(mock_sy):
    """get_tags returns empty list when no tags."""
    from mcp_siyuan.tools.smart import siyuan_get_tags

    mock_sy.call.return_value = {"tags": []}
    result = await siyuan_get_tags()
    assert result == []


@pytest.mark.asyncio
async def test_search_by_tag(mock_sy):
    """search_by_tag finds blocks with the given tag."""
    from mcp_siyuan.tools.smart import siyuan_search_by_tag

    mock_sy.call.return_value = [
        {"id": "b1", "content": "911 GT3 RS", "type": "p", "box": "nb1", "hpath": "/cars", "updated": "20260320"},
    ]
    result = await siyuan_search_by_tag(tag="porsche")
    assert len(result) == 1
    assert result[0]["content"] == "911 GT3 RS"
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "porsche" in stmt


@pytest.mark.asyncio
async def test_search_by_tag_rejects_injection(mock_sy):
    """search_by_tag rejects SQL injection attempts."""
    from mcp_siyuan.tools.smart import siyuan_search_by_tag

    with pytest.raises(ValueError, match="Unsafe characters"):
        await siyuan_search_by_tag(tag="'; DROP TABLE blocks; --")
    mock_sy.call.assert_not_called()


@pytest.mark.asyncio
async def test_get_block_children(mock_sy):
    """get_block_children returns tree structure using batch queries."""
    from mcp_siyuan.tools.smart import siyuan_get_block_children

    call_count = 0
    async def mock_call(endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        if endpoint == "/api/query/sql":
            stmt = kwargs.get("stmt", "")
            if "'doc1'" in stmt:
                return [
                    {"id": "h1", "content": "Heading 1", "type": "h", "sort": 0, "parent_id": "doc1"},
                    {"id": "p1", "content": "Paragraph", "type": "p", "sort": 1, "parent_id": "doc1"},
                ]
            else:
                return []
        elif endpoint == "/api/block/getBlockInfo":
            return {"content": "My Document", "type": "d"}
        return None

    mock_sy.call = mock_call
    result = await siyuan_get_block_children(id="doc1", depth=2)
    assert result["id"] == "doc1"
    assert result["type"] == "d"
    assert len(result["children"]) == 2
    assert result["children"][0]["content"] == "Heading 1"
    # With batch queries: 1 query for depth 1, 1 for depth 2 (h1+p1 children),
    # 1 for getBlockInfo = 3 total, NOT 1+N+1
    assert call_count == 3


@pytest.mark.asyncio
async def test_search_with_context(mock_sy):
    """search_with_context returns results with surrounding blocks."""
    from mcp_siyuan.tools.smart import siyuan_search_with_context

    call_count = 0
    async def mock_call(endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        if endpoint == "/api/search/fullTextSearchBlock":
            return {
                "blocks": [
                    {"id": "b2", "content": "Porsche 911", "type": "p", "hPath": "/cars", "box": "nb1", "rootID": "r1"},
                ]
            }
        elif endpoint == "/api/query/sql":
            return [
                {"id": "b1", "content": "German cars", "type": "h"},
                {"id": "b2", "content": "Porsche 911", "type": "p"},
                {"id": "b3", "content": "Amazing performance", "type": "p"},
            ]
        return None

    mock_sy.call = mock_call
    result = await siyuan_search_with_context(query="Porsche", context_blocks=1)
    assert len(result) == 1
    assert result[0]["content"] == "Porsche 911"
    assert "context" in result[0]
    assert len(result[0]["context"]) == 3  # b1, b2, b3


@pytest.mark.asyncio
async def test_search_with_context_no_context(mock_sy):
    """search_with_context works with context_blocks=0."""
    from mcp_siyuan.tools.smart import siyuan_search_with_context

    mock_sy.call.return_value = {
        "blocks": [
            {"id": "b1", "content": "test", "type": "p", "hPath": "/", "box": "nb1", "rootID": "r1"},
        ]
    }
    result = await siyuan_search_with_context(query="test", context_blocks=0)
    assert len(result) == 1
    assert "context" not in result[0]


@pytest.mark.asyncio
async def test_capture_task(mock_sy):
    """capture_task creates daily note and appends task."""
    from mcp_siyuan.tools.smart import siyuan_capture_task

    call_count = 0
    async def mock_call(endpoint, **kwargs):
        nonlocal call_count
        call_count += 1
        if endpoint == "/api/notebook/lsNotebooks":
            return {"notebooks": [{"id": "nb1", "name": "Work", "closed": False}]}
        elif endpoint == "/api/filetree/createDailyNote":
            return "daily-id-123"
        elif endpoint == "/api/block/appendBlock":
            assert "* [ ] Buy groceries" in kwargs.get("data", "")
            return [{"doOperations": [{"action": "insert"}]}]
        return None

    mock_sy.call = mock_call
    result = await siyuan_capture_task(text="Buy groceries")
    assert result["ok"] is True
    assert result["daily_note_id"] == "daily-id-123"
    assert result["task"] == "Buy groceries"


@pytest.mark.asyncio
async def test_capture_task_with_notebook(mock_sy):
    """capture_task skips notebook lookup when provided."""
    from mcp_siyuan.tools.smart import siyuan_capture_task

    calls = []
    async def mock_call(endpoint, **kwargs):
        calls.append(endpoint)
        if endpoint == "/api/filetree/createDailyNote":
            return "daily-id-456"
        elif endpoint == "/api/block/appendBlock":
            return [{"doOperations": [{"action": "insert"}]}]
        return None

    mock_sy.call = mock_call
    result = await siyuan_capture_task(text="Do stuff", notebook="nb2")
    assert result["ok"] is True
    assert "/api/notebook/lsNotebooks" not in calls


@pytest.mark.asyncio
async def test_get_document_outline(mock_sy):
    """get_document_outline returns headings only."""
    from mcp_siyuan.tools.smart import siyuan_get_document_outline

    mock_sy.call.return_value = [
        {"id": "h1", "content": "Introduction", "level": "h1", "sort": 0},
        {"id": "h2", "content": "Methods", "level": "h2", "sort": 10},
        {"id": "h3", "content": "Results", "level": "h2", "sort": 20},
    ]
    result = await siyuan_get_document_outline(id="doc1")
    assert len(result) == 3
    assert result[0]["content"] == "Introduction"
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "type = 'h'" in stmt


@pytest.mark.asyncio
async def test_sanitize_rejects_sql_injection():
    """_sanitize blocks dangerous SQL characters."""
    from mcp_siyuan.tools.smart import _sanitize

    with pytest.raises(ValueError, match="Unsafe characters"):
        _sanitize("'; DROP TABLE blocks; --")

    with pytest.raises(ValueError, match="Unsafe characters"):
        _sanitize('foo"bar')

    with pytest.raises(ValueError, match="Unsafe characters"):
        _sanitize("foo /* comment */")

    # Clean values should pass through
    assert _sanitize("normal-notebook-id") == "normal-notebook-id"
    assert _sanitize("20260320152120-abc123") == "20260320152120-abc123"
