"""Tests for high-level smart tools."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_sy():
    # get_block_children reuses read.get_block, so both modules share the mock.
    with patch("mcp_siyuan.tools.smart.sy") as mock, patch("mcp_siyuan.tools.read.sy", mock):
        mock.call = AsyncMock()
        yield mock


@pytest.mark.asyncio
async def test_get_recent_docs(mock_sy):
    """get_recent_docs returns recent documents."""
    from mcp_siyuan.tools.smart import get_recent_docs

    mock_sy.call.return_value = [
        {"id": "d1", "title": "Meeting Notes", "box": "nb1", "hpath": "/notes", "updated": "20260320"},
        {"id": "d2", "title": "TODO List", "box": "nb1", "hpath": "/tasks", "updated": "20260319"},
    ]
    result = await get_recent_docs(limit=5)
    assert len(result) == 2
    assert result[0].title == "Meeting Notes"


@pytest.mark.asyncio
async def test_get_recent_docs_filtered_by_notebook(mock_sy):
    """get_recent_docs filters by notebook when provided."""
    from mcp_siyuan.tools.smart import get_recent_docs

    mock_sy.call.return_value = []
    await get_recent_docs(notebook="nb1")
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "nb1" in stmt


@pytest.mark.asyncio
async def test_list_documents_populates_name(mock_sy):
    """list_documents projects the title into both title and name (CDI-1093)."""
    from mcp_siyuan.tools.smart import list_documents

    mock_sy.call.return_value = [
        {"id": "d1", "title": "Quarterly Review", "box": "nb1", "hpath": "/q", "updated": "20260601"},
    ]
    result = await list_documents()
    assert len(result) == 1
    assert result[0].title == "Quarterly Review"
    # name is never blank — it mirrors the title (raw SQL name column would be empty).
    assert result[0].name == "Quarterly Review"
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "type = 'd'" in stmt


@pytest.mark.asyncio
async def test_list_documents_filters_by_title_and_notebook(mock_sy):
    """list_documents builds a title LIKE + notebook filter."""
    from mcp_siyuan.tools.smart import list_documents

    mock_sy.call.return_value = []
    await list_documents(title_contains="Review", notebook="nb1")
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "content LIKE '%Review%'" in stmt
    assert "box = 'nb1'" in stmt


@pytest.mark.asyncio
async def test_list_documents_rejects_injection(mock_sy):
    """list_documents sanitizes the title filter (CDI-1093)."""
    from mcp_siyuan.tools.smart import list_documents

    with pytest.raises(ValueError, match="Unsafe characters"):
        await list_documents(title_contains="'; DROP TABLE blocks; --")
    mock_sy.call.assert_not_called()


@pytest.mark.asyncio
async def test_find_tasks_open(mock_sy):
    """find_tasks returns open tasks with doc_title."""
    from mcp_siyuan.tools.smart import find_tasks

    mock_sy.call.return_value = [
        {"id": "t1", "content": "Buy groceries", "box": "nb1", "hpath": "/daily/2026-03-20", "root_id": "r1", "updated": "20260320", "doc_title": "Daily Note"},
    ]
    result = await find_tasks()
    assert len(result) == 1
    assert result[0].content == "Buy groceries"
    assert result[0].doc_title == "Daily Note"
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "'t'" in stmt  # unchecked subtype
    assert "doc_title" in stmt  # JOIN for doc title


@pytest.mark.asyncio
async def test_find_tasks_checked(mock_sy):
    """find_tasks can return completed tasks."""
    from mcp_siyuan.tools.smart import find_tasks

    mock_sy.call.return_value = []
    await find_tasks(checked=True)
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "'d'" in stmt  # checked subtype


@pytest.mark.asyncio
async def test_find_tasks_scoped_to_notebook(mock_sy):
    """find_tasks filters by notebook."""
    from mcp_siyuan.tools.smart import find_tasks

    mock_sy.call.return_value = []
    await find_tasks(notebook="nb1")
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "nb1" in stmt


@pytest.mark.asyncio
async def test_get_backlinks(mock_sy):
    """get_backlinks returns referencing blocks with doc_title."""
    from mcp_siyuan.tools.smart import get_backlinks

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
    result = await get_backlinks(id="doc1")
    assert len(result) == 2
    assert result[0].content == "See also [[doc]]"
    assert result[0].doc_title == "Notes Document"


@pytest.mark.asyncio
async def test_get_backlinks_empty(mock_sy):
    """get_backlinks returns empty list when no refs."""
    from mcp_siyuan.tools.smart import get_backlinks

    mock_sy.call.return_value = {"backlinks": []}
    result = await get_backlinks(id="orphan")
    assert result == []


@pytest.mark.asyncio
async def test_get_tags(mock_sy):
    """get_tags flattens nested tag tree."""
    from mcp_siyuan.tools.smart import get_tags

    mock_sy.call.return_value = {
        "tags": [
            {"label": "cars", "count": 5, "tags": [
                {"label": "porsche", "count": 3, "tags": []},
            ]},
            {"label": "wishlist", "count": 2, "tags": []},
        ]
    }
    result = await get_tags()
    assert len(result) == 3
    flat = {(t.tag, t.count) for t in result}
    assert ("cars", 5) in flat
    assert ("cars/porsche", 3) in flat
    assert ("wishlist", 2) in flat


@pytest.mark.asyncio
async def test_get_tags_empty(mock_sy):
    """get_tags returns empty list when no tags."""
    from mcp_siyuan.tools.smart import get_tags

    mock_sy.call.return_value = {"tags": []}
    result = await get_tags()
    assert result == []


@pytest.mark.asyncio
async def test_search_by_tag(mock_sy):
    """search_by_tag finds blocks with the given tag."""
    from mcp_siyuan.tools.smart import search_by_tag

    mock_sy.call.return_value = [
        {"id": "b1", "content": "911 GT3 RS", "type": "p", "box": "nb1", "hpath": "/cars", "updated": "20260320"},
    ]
    result = await search_by_tag(tag="porsche")
    assert len(result) == 1
    assert result[0].content == "911 GT3 RS"
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "porsche" in stmt


@pytest.mark.asyncio
async def test_search_by_tag_matches_textmark_variants(mock_sy):
    """search_by_tag covers API-created textmark tag spans, not just legacy 'tag' (CDI-1228)."""
    from mcp_siyuan.tools.smart import search_by_tag

    mock_sy.call.return_value = []
    await search_by_tag(tag="decision")
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    # Predicate must cover all known tag span types, not only the legacy bare 'tag'.
    assert "spans.type IN ('tag', 'textmark tag', 'textmark em tag')" in stmt
    # No blind LIKE '%tag%' on the span type.
    assert "spans.type = 'tag'" not in stmt


@pytest.mark.asyncio
async def test_search_by_tag_exact_name_match(mock_sy):
    """search_by_tag anchors the tag name exactly on span content — no substring leak (CDI-1228)."""
    from mcp_siyuan.tools.smart import search_by_tag

    mock_sy.call.return_value = []
    await search_by_tag(tag="decision")
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    # Exact equality on content, not a substring LIKE that would also match 'decisions'.
    assert "spans.content = 'decision'" in stmt
    assert "LIKE" not in stmt.upper()


@pytest.mark.asyncio
async def test_search_by_tag_rejects_injection(mock_sy):
    """search_by_tag rejects SQL injection attempts."""
    from mcp_siyuan.tools.smart import search_by_tag

    with pytest.raises(ValueError, match="Unsafe characters"):
        await search_by_tag(tag="'; DROP TABLE blocks; --")
    mock_sy.call.assert_not_called()


@pytest.mark.asyncio
async def test_search_with_context(mock_sy):
    """search_with_context returns results with surrounding blocks."""
    from mcp_siyuan.tools.smart import search_with_context

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
    result = await search_with_context(query="Porsche", context_blocks=1)
    assert len(result) == 1
    assert result[0].content == "Porsche 911"
    assert len(result[0].context) == 3  # b1, b2, b3


@pytest.mark.asyncio
async def test_search_with_context_no_context(mock_sy):
    """search_with_context works with context_blocks=0."""
    from mcp_siyuan.tools.smart import search_with_context

    mock_sy.call.return_value = {
        "blocks": [
            {"id": "b1", "content": "test", "type": "p", "hPath": "/", "box": "nb1", "rootID": "r1"},
        ]
    }
    result = await search_with_context(query="test", context_blocks=0)
    assert len(result) == 1
    # With context_blocks=0, no siblings are fetched; context defaults to [].
    assert result[0].context == []


@pytest.mark.asyncio
async def test_capture_task(mock_sy):
    """capture_task creates daily note and appends task."""
    from mcp_siyuan.tools.smart import capture_task

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
    result = await capture_task(text="Buy groceries")
    assert result.ok is True
    assert result.daily_note_id == "daily-id-123"
    assert result.task == "Buy groceries"


@pytest.mark.asyncio
async def test_capture_task_with_notebook(mock_sy):
    """capture_task skips notebook lookup when provided."""
    from mcp_siyuan.tools.smart import capture_task

    calls = []
    async def mock_call(endpoint, **kwargs):
        calls.append(endpoint)
        if endpoint == "/api/filetree/createDailyNote":
            return "daily-id-456"
        elif endpoint == "/api/block/appendBlock":
            return [{"doOperations": [{"action": "insert"}]}]
        return None

    mock_sy.call = mock_call
    result = await capture_task(text="Do stuff", notebook="nb2")
    assert result.ok is True
    assert "/api/notebook/lsNotebooks" not in calls


@pytest.mark.asyncio
async def test_get_document_outline(mock_sy):
    """Headings come back in document order, not blocks.sort order.

    Real index rows all carry sort=5 for headings, so SQL order is arbitrary;
    here the index returns them scrambled and the kernel child list is the
    truth. A heading nested in a blockquote (not a direct child) is kept.
    """
    from mcp_siyuan.tools.smart import get_document_outline

    kernel = [
        {"id": "h1", "type": "h", "subType": "h1", "content": "Introduction"},
        {"id": "p1", "type": "p", "content": "text"},
        {"id": "h2", "type": "h", "subType": "h2", "content": "Methods"},
        {"id": "h3", "type": "h", "subType": "h2", "content": "Results"},
    ]
    index = [
        {"id": "h3", "content": "Results", "level": "h2"},
        {"id": "hq", "content": "Quoted", "level": "h3"},
        {"id": "h1", "content": "Introduction", "level": "h1"},
        {"id": "h2", "content": "Methods", "level": "h2"},
    ]

    async def mock_call(endpoint, **kwargs):
        return kernel if endpoint == "/api/block/getChildBlocks" else index

    mock_sy.call = mock_call
    result = await get_document_outline(id="doc1")
    assert [h.content for h in result] == ["Introduction", "Methods", "Results", "Quoted"]
    assert [h.sort for h in result] == [0, 1, 2, 3]
    assert result[0].level == "h1"


@pytest.mark.asyncio
async def test_doc_exists_found(mock_sy):
    """doc_exists returns block_id when the doc is present."""
    from mcp_siyuan.tools.smart import doc_exists

    mock_sy.call.return_value = [{"id": "doc-abc"}]
    result = await doc_exists(notebook="nb1", path="/Projects/Foo")
    assert result.exists is True
    assert result.block_id == "doc-abc"
    assert result.hpath == "/Projects/Foo"
    assert result.error is None
    stmt = mock_sy.call.call_args.kwargs["stmt"]
    assert "box = 'nb1'" in stmt
    assert "hpath = '/Projects/Foo'" in stmt


@pytest.mark.asyncio
async def test_doc_exists_missing(mock_sy):
    """doc_exists returns exists=False when no match — no error."""
    from mcp_siyuan.tools.smart import doc_exists

    mock_sy.call.return_value = []
    result = await doc_exists(notebook="nb1", path="/missing")
    assert result.exists is False
    assert result.block_id is None
    assert result.hpath == "/missing"
    assert result.error is None


@pytest.mark.asyncio
async def test_doc_exists_normalises_path(mock_sy):
    """doc_exists prepends a leading slash if missing."""
    from mcp_siyuan.tools.smart import doc_exists

    mock_sy.call.return_value = []
    result = await doc_exists(notebook="nb1", path="Projects/Foo")
    assert result.hpath == "/Projects/Foo"


@pytest.mark.asyncio
async def test_list_conflicts_flags_sync_and_malformed(mock_sy):
    """list_conflicts flags sync-conflict suffixes and malformed hpaths (CDI-1093)."""
    from mcp_siyuan.tools.smart import list_conflicts

    mock_sy.call.return_value = [
        {"id": "d1", "title": "Notes (conflict 2026-06)", "box": "nb1", "hpath": "/Notes (conflict 2026-06)", "path": "/x.sy"},
        {"id": "d2", "title": "Bad", "box": "nb1", "hpath": "", "path": ""},
        {"id": "d3", "title": "Fine", "box": "nb1", "hpath": "/Fine", "path": "/fine.sy"},
    ]
    result = await list_conflicts()
    by_id = {d.id: d.reason for d in result}
    assert by_id.get("d1") == "sync_conflict"
    assert by_id.get("d2") == "malformed_hpath"
    assert "d3" not in by_id  # clean doc not flagged


@pytest.mark.asyncio
async def test_list_orphans_detects_missing_parent(mock_sy):
    """list_orphans flags nested docs whose parent path is absent (CDI-1093)."""
    from mcp_siyuan.tools.smart import list_orphans

    mock_sy.call.return_value = [
        {"id": "p", "title": "Projects", "box": "nb1", "hpath": "/Projects", "path": "/p.sy"},
        {"id": "child_ok", "title": "Has Parent", "box": "nb1", "hpath": "/Projects/Foo", "path": "/p/f.sy"},
        {"id": "orphan", "title": "Lost", "box": "nb1", "hpath": "/Gone/Bar", "path": "/g/b.sy"},
        {"id": "toplevel", "title": "Root", "box": "nb1", "hpath": "/Root", "path": "/r.sy"},
    ]
    result = await list_orphans()
    ids = {d.id for d in result}
    assert ids == {"orphan"}  # only the doc whose parent '/Gone' is missing
    assert result[0].reason == "orphan"


@pytest.mark.asyncio
async def test_get_doc_summary(mock_sy):
    """get_doc_summary returns title, child_count, preview, first blocks (CDI-1093)."""
    from mcp_siyuan.tools.smart import get_doc_summary

    async def mock_call(endpoint, **kwargs):
        stmt = kwargs.get("stmt", "")
        if "type = 'd'" in stmt:
            return [{"id": "doc1", "title": "My Doc", "hpath": "/My Doc", "box": "nb1"}]
        if "COUNT(*)" in stmt:
            return [{"n": 3}]
        # first-N blocks query
        return [
            {"id": "b1", "type": "h", "content": "Intro", "sort": 0},
            {"id": "b2", "type": "p", "content": "Body text", "sort": 1},
        ]

    mock_sy.call.side_effect = mock_call
    result = await get_doc_summary(id="doc1")
    assert result.title == "My Doc"
    assert result.hpath == "/My Doc"
    assert result.child_count == 3
    assert len(result.first_blocks) == 2
    assert "Intro" in result.content_preview
    assert result.error is None


@pytest.mark.asyncio
async def test_get_doc_summary_not_found(mock_sy):
    """get_doc_summary raises ToolError when the doc is missing (CDI-1093)."""
    from fastmcp.exceptions import ToolError

    from mcp_siyuan.tools.smart import get_doc_summary

    mock_sy.call.return_value = []
    with pytest.raises(ToolError, match="not found"):
        await get_doc_summary(id="nope")


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


@pytest.mark.asyncio
async def test_get_block_children_real_content_in_document_order(mock_sy):
    """Root carries real type/content (getBlockInfo has neither) and children
    come in document order from the kernel child list, not by ``sort`` (a
    block-type weight). Headings are leaves here: their section blocks are
    already siblings, so recursing would list them twice."""
    from mcp_siyuan.tools.smart import get_block_children

    kids = {
        "doc1": [
            {"id": "p0", "type": "p", "content": "Intro"},
            {"id": "h1", "type": "h", "subType": "h2", "content": "Heading"},
            {"id": "l1", "type": "l", "subType": "u", "content": ""},
        ],
        "l1": [{"id": "i1", "type": "i", "content": "", "markdown": "- item"}],
        "h1": [{"id": "l1", "type": "l"}],
    }

    async def mock_call(endpoint, **kwargs):
        if endpoint == "/api/query/sql":
            return [{"id": "doc1", "type": "d", "content": "My Document", "parent_id": ""}]
        if endpoint == "/api/block/getBlockKramdown":
            return {"id": "doc1", "kramdown": "My Document"}
        if endpoint == "/api/block/getChildBlocks":
            return kids.get(kwargs["id"], [])
        if endpoint == "/api/block/getBlockInfo":
            return {"rootID": "doc1", "box": "nb"}  # no type, no content
        raise AssertionError(endpoint)

    mock_sy.call = mock_call
    result = await get_block_children(id="doc1", depth=3)
    assert (result.type, result.content) == ("d", "My Document")
    assert [c["id"] for c in result.children] == ["p0", "h1", "l1"]
    assert [c["sort"] for c in result.children] == [0, 1, 2]
    assert result.children[0]["content"] == "Intro"
    assert result.children[1]["children"] == []
    item = result.children[2]["children"][0]
    assert (item["id"], item["content"], item["parent_id"]) == ("i1", "- item", "l1")
