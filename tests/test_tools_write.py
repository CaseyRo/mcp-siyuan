"""Tests for Tier 2 write tools."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_sy():
    with patch("mcp_siyuan.tools.write.sy") as mock:
        mock.call = AsyncMock()
        yield mock


@pytest.mark.asyncio
async def test_create_notebook(mock_sy):
    """create_notebook returns notebook object with ID."""
    from mcp_siyuan.tools.write import create_notebook

    mock_sy.call.return_value = {
        "notebook": {"id": "20260326100000-abc1234", "name": "Test Notebook"}
    }
    result = await create_notebook(name="Test Notebook")
    assert result["notebook"]["id"] == "20260326100000-abc1234"
    mock_sy.call.assert_called_once_with(
        "/api/notebook/createNotebook",
        name="Test Notebook",
    )


@pytest.mark.asyncio
async def test_create_notebook_null_response(mock_sy):
    """create_notebook handles null data response."""
    from mcp_siyuan.tools.write import create_notebook

    mock_sy.call.return_value = None
    result = await create_notebook(name="Another Notebook")
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_rename_notebook(mock_sy):
    """rename_notebook sends notebook ID and new name."""
    from mcp_siyuan.tools.write import rename_notebook

    mock_sy.call.return_value = None
    result = await rename_notebook(notebook="nb1", name="New Name")
    assert result == {"ok": True}
    mock_sy.call.assert_called_once_with(
        "/api/notebook/renameNotebook",
        notebook="nb1",
        name="New Name",
    )


@pytest.mark.asyncio
async def test_remove_notebook(mock_sy):
    """remove_notebook sends notebook ID."""
    from mcp_siyuan.tools.write import remove_notebook

    mock_sy.call.return_value = None
    result = await remove_notebook(notebook="nb1")
    assert result == {"ok": True}
    mock_sy.call.assert_called_once_with(
        "/api/notebook/removeNotebook",
        notebook="nb1",
    )


@pytest.mark.asyncio
async def test_create_document(mock_sy):
    """create_document returns new doc ID."""
    from mcp_siyuan.tools.write import create_document

    mock_sy.call.return_value = "20210914223645-oj2vnx2"
    result = await create_document(
        notebook="nb1", path="/test/doc", markdown="# Hello"
    )
    assert result == "20210914223645-oj2vnx2"
    mock_sy.call.assert_called_once_with(
        "/api/filetree/createDocWithMd",
        notebook="nb1",
        path="/test/doc",
        markdown="# Hello",
    )


@pytest.mark.asyncio
async def test_create_document_empty(mock_sy):
    """create_document works without markdown content."""
    from mcp_siyuan.tools.write import create_document

    mock_sy.call.return_value = "doc-id-123"
    result = await create_document(notebook="nb1", path="/empty")
    assert result == "doc-id-123"


@pytest.mark.asyncio
async def test_update_block(mock_sy):
    """update_block sends correct payload and wraps list result."""
    from mcp_siyuan.tools.write import update_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "update"}]}]
    result = await update_block(id="b1", data="updated text")
    assert result["ok"] is True
    assert "transactions" in result
    mock_sy.call.assert_called_once_with(
        "/api/block/updateBlock",
        id="b1",
        data="updated text",
        dataType="markdown",
    )


@pytest.mark.asyncio
async def test_insert_block_after_new_interface(mock_sy):
    """insert_block with position='after' and anchor_id."""
    from mcp_siyuan.tools.write import insert_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "insert", "id": "new1"}]}]
    await insert_block(data="new paragraph", position="after", anchor_id="b1")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("previousID") == "b1"


@pytest.mark.asyncio
async def test_insert_block_before_new_interface(mock_sy):
    """insert_block with position='before' and anchor_id."""
    from mcp_siyuan.tools.write import insert_block

    mock_sy.call.return_value = {"ok": True}
    await insert_block(data="before this", position="before", anchor_id="b2")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("nextID") == "b2"


@pytest.mark.asyncio
async def test_insert_block_child_new_interface(mock_sy):
    """insert_block with position='child' and anchor_id."""
    from mcp_siyuan.tools.write import insert_block

    mock_sy.call.return_value = {"ok": True}
    await insert_block(data="child block", position="child", anchor_id="doc1")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("parentID") == "doc1"


@pytest.mark.asyncio
async def test_insert_block_legacy_previous_id(mock_sy):
    """insert_block still works with legacy previous_id param."""
    from mcp_siyuan.tools.write import insert_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "insert", "id": "new1"}]}]
    await insert_block(data="new paragraph", previous_id="b1")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("previousID") == "b1"


@pytest.mark.asyncio
async def test_insert_block_legacy_next_id(mock_sy):
    """insert_block still works with legacy next_id param."""
    from mcp_siyuan.tools.write import insert_block

    mock_sy.call.return_value = {"ok": True}
    await insert_block(data="before this", next_id="b2")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("nextID") == "b2"


@pytest.mark.asyncio
async def test_insert_block_legacy_parent_id(mock_sy):
    """insert_block still works with legacy parent_id param."""
    from mcp_siyuan.tools.write import insert_block

    mock_sy.call.return_value = {"ok": True}
    await insert_block(data="child block", parent_id="doc1")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("parentID") == "doc1"


@pytest.mark.asyncio
async def test_append_block(mock_sy):
    """append_block sends parent_id correctly."""
    from mcp_siyuan.tools.write import append_block

    mock_sy.call.return_value = {"ok": True}
    await append_block(parent_id="doc1", data="appended text")
    mock_sy.call.assert_called_once_with(
        "/api/block/appendBlock",
        data="appended text",
        dataType="markdown",
        parentID="doc1",
    )


@pytest.mark.asyncio
async def test_delete_block(mock_sy):
    """delete_block sends correct payload."""
    from mcp_siyuan.tools.write import delete_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "delete"}]}]
    result = await delete_block(id="b1")
    assert result["ok"] is True
    mock_sy.call.assert_called_once_with("/api/block/deleteBlock", id="b1")


@pytest.mark.asyncio
async def test_delete_block_already_absent(mock_sy):
    """delete_block returns success when block is already gone (idempotent)."""
    from mcp_siyuan.client import SiYuanError
    from mcp_siyuan.tools.write import delete_block

    mock_sy.call.side_effect = SiYuanError("block not found", code=-1)
    result = await delete_block(id="missing-block")
    assert result["ok"] is True
    assert result.get("already_absent") is True


@pytest.mark.asyncio
async def test_delete_block_idempotency_key(mock_sy):
    """delete_block with idempotency_key replays from cache on second call."""
    from mcp_siyuan.idempotency import cache as idempotency_cache
    from mcp_siyuan.tools.write import delete_block

    idempotency_cache.reset_for_tests(ttl_seconds=300)
    mock_sy.call.return_value = [{"doOperations": [{"action": "delete"}]}]

    result1 = await delete_block(id="b2", idempotency_key="del-b2-v1")
    result2 = await delete_block(id="b2", idempotency_key="del-b2-v1")

    assert result1["ok"] is True
    assert result2["ok"] is True
    # Second call hits cache — kernel is only called once
    mock_sy.call.assert_called_once()


@pytest.mark.asyncio
async def test_set_block_attrs(mock_sy):
    """set_block_attrs sends attrs dict."""
    from mcp_siyuan.tools.write import set_block_attrs

    mock_sy.call.return_value = None
    await set_block_attrs(id="b1", attrs={"custom-status": "done"})
    mock_sy.call.assert_called_once_with(
        "/api/attr/setBlockAttrs",
        id="b1",
        attrs={"custom-status": "done"},
    )


@pytest.mark.asyncio
async def test_move_doc_single(mock_sy):
    """move_doc sends single doc ID to moveDocsByID."""
    from mcp_siyuan.tools.write import move_doc

    mock_sy.call.return_value = None
    result = await move_doc(from_ids=["doc1"], to_id="notebook1")
    assert result == {"ok": True}
    mock_sy.call.assert_called_once_with(
        "/api/filetree/moveDocsByID",
        fromIDs=["doc1"],
        toID="notebook1",
    )


@pytest.mark.asyncio
async def test_move_doc_multiple(mock_sy):
    """move_doc supports moving multiple documents at once."""
    from mcp_siyuan.tools.write import move_doc

    mock_sy.call.return_value = None
    result = await move_doc(from_ids=["doc1", "doc2"], to_id="parent-doc")
    assert result == {"ok": True}
    mock_sy.call.assert_called_once_with(
        "/api/filetree/moveDocsByID",
        fromIDs=["doc1", "doc2"],
        toID="parent-doc",
    )


@pytest.mark.asyncio
async def test_rename_doc(mock_sy):
    """rename_doc sends id and title to renameDocByID."""
    from mcp_siyuan.tools.write import rename_doc

    mock_sy.call.return_value = None
    result = await rename_doc(id="doc1", title="New Title")
    assert result == {"ok": True}
    mock_sy.call.assert_called_once_with(
        "/api/filetree/renameDocByID",
        id="doc1",
        title="New Title",
    )


@pytest.mark.asyncio
async def test_move_block_previous(mock_sy):
    """move_block with previous_id sends correct payload."""
    from mcp_siyuan.tools.write import move_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "move"}]}]
    result = await move_block(id="block1", previous_id="sibling1")
    assert result["ok"] is True
    mock_sy.call.assert_called_once_with(
        "/api/block/moveBlock",
        id="block1",
        parentID="",
        previousID="sibling1",
    )


@pytest.mark.asyncio
async def test_move_block_parent(mock_sy):
    """move_block with parent_id sends correct payload."""
    from mcp_siyuan.tools.write import move_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "move"}]}]
    result = await move_block(id="block1", parent_id="parent1")
    assert result["ok"] is True
    mock_sy.call.assert_called_once_with(
        "/api/block/moveBlock",
        id="block1",
        parentID="parent1",
        previousID="",
    )


@pytest.mark.asyncio
async def test_move_block_both(mock_sy):
    """move_block with both previous_id and parent_id sends both."""
    from mcp_siyuan.tools.write import move_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "move"}]}]
    result = await move_block(
        id="block1", previous_id="sibling1", parent_id="parent1"
    )
    assert result["ok"] is True
    mock_sy.call.assert_called_once_with(
        "/api/block/moveBlock",
        id="block1",
        parentID="parent1",
        previousID="sibling1",
    )


@pytest.mark.asyncio
async def test_move_block_no_anchor(mock_sy):
    """move_block raises ValueError when no anchor is provided."""
    from mcp_siyuan.tools.write import move_block

    with pytest.raises(ValueError, match="At least one of"):
        await move_block(id="block1")


@pytest.mark.asyncio
async def test_daily_note(mock_sy):
    """daily_note returns document ID."""
    from mcp_siyuan.tools.write import daily_note

    mock_sy.call.return_value = "daily-note-id"
    result = await daily_note(notebook="nb1")
    assert result == "daily-note-id"
    mock_sy.call.assert_called_once_with(
        "/api/filetree/createDailyNote",
        notebook="nb1",
    )


@pytest.mark.asyncio
async def test_daily_note_auto_notebook(mock_sy):
    """daily_note picks first open notebook when none specified."""
    from mcp_siyuan.tools.write import daily_note

    calls = []
    async def mock_call(endpoint, **kwargs):
        calls.append(endpoint)
        if endpoint == "/api/notebook/lsNotebooks":
            return {"notebooks": [
                {"id": "nb1", "name": "Work", "closed": False},
                {"id": "nb2", "name": "Archive", "closed": True},
            ]}
        elif endpoint == "/api/filetree/createDailyNote":
            assert kwargs["notebook"] == "nb1"
            return "daily-auto-id"
        return None

    mock_sy.call = mock_call
    result = await daily_note()
    assert result == "daily-auto-id"


# --- bulk operations (CDI-1053) ---


@pytest.mark.asyncio
async def test_bulk_create_documents_mixed_results(mock_sy):
    """bulk_create_documents reports per-item status; failures don't abort."""
    from mcp_siyuan.client import SiYuanError
    from mcp_siyuan.tools.write import bulk_create_documents

    # First create returns an ID; second raises; third returns an ID.
    call_iter = iter([
        "id-a",
        SiYuanError("conflict", code=-1),
        "id-c",
    ])

    async def mock_call(endpoint, **kwargs):
        nxt = next(call_iter)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    mock_sy.call = mock_call
    results = await bulk_create_documents(documents=[
        {"notebook": "nb1", "path": "/a", "markdown": "A"},
        {"notebook": "nb1", "path": "/b"},
        {"notebook": "nb1", "path": "/c"},
    ])
    assert [r.status for r in results] == ["ok", "error", "ok"]
    assert results[0].block_id == "id-a"
    assert "conflict" in (results[1].error or "")
    assert results[2].block_id == "id-c"


@pytest.mark.asyncio
async def test_bulk_create_documents_missing_fields(mock_sy):
    """bulk_create_documents reports validation errors per-item."""
    from mcp_siyuan.tools.write import bulk_create_documents

    mock_sy.call = AsyncMock(return_value="never-called")
    results = await bulk_create_documents(documents=[
        {"notebook": "", "path": "/a"},
        {"notebook": "nb1", "path": ""},
    ])
    assert all(r.status == "error" for r in results)
    assert "required" in (results[0].error or "")


@pytest.mark.asyncio
async def test_bulk_create_documents_caps_size(mock_sy):
    """Batches over 50 items are rejected."""
    from mcp_siyuan.tools.write import bulk_create_documents

    docs = [{"notebook": "nb1", "path": f"/d{i}"} for i in range(51)]
    with pytest.raises(ValueError, match="exceeds limit"):
        await bulk_create_documents(documents=docs)


@pytest.mark.asyncio
async def test_bulk_set_attrs_mixed_results(mock_sy):
    """bulk_set_attrs reports per-item success/failure."""
    from mcp_siyuan.client import SiYuanError
    from mcp_siyuan.tools.write import bulk_set_attrs

    call_iter = iter([None, SiYuanError("bad attr", code=-1)])

    async def mock_call(endpoint, **kwargs):
        nxt = next(call_iter)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    mock_sy.call = mock_call
    results = await bulk_set_attrs(items=[
        {"block_id": "b1", "attrs": {"custom-x": "1"}},
        {"block_id": "b2", "attrs": {"custom-y": "2"}},
    ])
    assert [r.status for r in results] == ["ok", "error"]
    assert results[1].block_id == "b2"


# --- upsert_section + append_to_section (CDI-1050 / CDI-1052) ---


# A small fixture document at parent=doc1, ordered by sort:
#   h1 (subtype h2) "Project Identity"
#   p1 paragraph
#   h2 (subtype h3) "Sub"  (still inside Project Identity)
#   p2 paragraph
#   h3 (subtype h2) "DoD"
#   p3 paragraph
_SECTION_BLOCKS = [
    {"id": "h1", "type": "h", "subtype": "h2", "content": "Project Identity", "sort": 0},
    {"id": "p1", "type": "p", "subtype": "", "content": "line one", "sort": 10},
    {"id": "h2", "type": "h", "subtype": "h3", "content": "Sub", "sort": 20},
    {"id": "p2", "type": "p", "subtype": "", "content": "sub line", "sort": 30},
    {"id": "h3", "type": "h", "subtype": "h2", "content": "DoD", "sort": 40},
    {"id": "p3", "type": "p", "subtype": "", "content": "dod line", "sort": 50},
]


@pytest.mark.asyncio
async def test_upsert_section_replaces_existing(mock_sy):
    """upsert_section deletes existing section blocks and inserts new content."""
    from mcp_siyuan.tools.write import upsert_section

    calls: list[tuple[str, dict]] = []

    async def mock_call(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        if endpoint == "/api/query/sql":
            return _SECTION_BLOCKS
        return None

    mock_sy.call = mock_call
    result = await upsert_section(
        doc_id="doc1",
        section_heading="Project Identity",
        markdown="New content here",
    )
    assert result["ok"] is True
    assert result["action"] == "replaced"
    assert result["heading_id"] == "h1"

    deletes = [c for c in calls if c[0] == "/api/block/deleteBlock"]
    # Section content under h1 (subtype h2) runs until h3 (subtype h2):
    # → p1, h2, p2 (3 blocks)
    deleted_ids = [d[1]["id"] for d in deletes]
    assert set(deleted_ids) == {"p1", "h2", "p2"}

    inserts = [c for c in calls if c[0] == "/api/block/insertBlock"]
    assert inserts
    assert inserts[0][1]["previousID"] == "h1"
    assert inserts[0][1]["data"] == "New content here"


@pytest.mark.asyncio
async def test_upsert_section_creates_when_missing(mock_sy):
    """upsert_section appends a new heading + body when no match."""
    from mcp_siyuan.tools.write import upsert_section

    calls: list[tuple[str, dict]] = []

    async def mock_call(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        if endpoint == "/api/query/sql":
            return _SECTION_BLOCKS
        return None

    mock_sy.call = mock_call
    result = await upsert_section(
        doc_id="doc1",
        section_heading="Brand New",
        markdown="Body",
        heading_level=2,
    )
    assert result["action"] == "created"
    appends = [c for c in calls if c[0] == "/api/block/appendBlock"]
    assert appends
    appended = appends[0][1]["data"]
    assert appended.startswith("## Brand New")
    assert "Body" in appended
    assert appends[0][1]["parentID"] == "doc1"


@pytest.mark.asyncio
async def test_upsert_section_case_and_whitespace_tolerant(mock_sy):
    """Heading match is case-insensitive and whitespace-tolerant."""
    from mcp_siyuan.tools.write import upsert_section

    async def mock_call(endpoint, **kwargs):
        if endpoint == "/api/query/sql":
            return _SECTION_BLOCKS
        return None

    mock_sy.call = mock_call
    result = await upsert_section(
        doc_id="doc1",
        section_heading="  project   IDENTITY ",
        markdown="X",
    )
    assert result["action"] == "replaced"
    assert result["heading_id"] == "h1"


@pytest.mark.asyncio
async def test_append_to_section_inserts_after_last_block(mock_sy):
    """append_to_section inserts after the last block in the section."""
    from mcp_siyuan.tools.write import append_to_section

    calls: list[tuple[str, dict]] = []

    async def mock_call(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        if endpoint == "/api/query/sql":
            return _SECTION_BLOCKS
        return None

    mock_sy.call = mock_call
    result = await append_to_section(
        doc_id="doc1",
        section_heading="Project Identity",
        markdown="appended line",
    )
    assert result["ok"] is True
    # Last block of "Project Identity" section is p2 (h2 ends section).
    assert result["anchor_id"] == "p2"
    inserts = [c for c in calls if c[0] == "/api/block/insertBlock"]
    assert inserts and inserts[0][1]["previousID"] == "p2"
    assert inserts[0][1]["data"] == "appended line"


@pytest.mark.asyncio
async def test_append_to_section_errors_on_missing_heading(mock_sy):
    """append_to_section raises when the heading is not found."""
    from mcp_siyuan.tools.write import append_to_section

    async def mock_call(endpoint, **kwargs):
        if endpoint == "/api/query/sql":
            return _SECTION_BLOCKS
        return None

    mock_sy.call = mock_call
    with pytest.raises(ValueError, match="not found"):
        await append_to_section(
            doc_id="doc1", section_heading="Missing", markdown="x"
        )


@pytest.mark.asyncio
async def test_append_to_section_empty_section(mock_sy):
    """When section has no body blocks, anchor falls back to heading id."""
    from mcp_siyuan.tools.write import append_to_section

    only_heading = [
        {"id": "h-only", "type": "h", "subtype": "h2", "content": "Empty", "sort": 0},
    ]

    async def mock_call(endpoint, **kwargs):
        if endpoint == "/api/query/sql":
            return only_heading
        return None

    mock_sy.call = mock_call
    result = await append_to_section(
        doc_id="doc1", section_heading="Empty", markdown="first"
    )
    assert result["anchor_id"] == "h-only"


# --- get_or_create_doc (CDI-1051) ---


@pytest.mark.asyncio
async def test_get_or_create_doc_creates_when_missing(mock_sy):
    """get_or_create_doc creates a new doc when none exists."""
    from mcp_siyuan.tools.write import get_or_create_doc

    responses = [
        [],  # SQL lookup returns empty
        "new-doc-id",  # createDocWithMd
    ]

    async def mock_call(endpoint, **kwargs):
        return responses.pop(0)

    mock_sy.call = mock_call
    result = await get_or_create_doc(
        notebook="nb1", path="/Projects/New", markdown="# New"
    )
    assert result.block_id == "new-doc-id"
    assert result.was_created is True
    assert result.was_updated is False
    assert result.hpath == "/Projects/New"


@pytest.mark.asyncio
async def test_get_or_create_doc_returns_existing(mock_sy):
    """get_or_create_doc returns existing block_id without re-creating."""
    from mcp_siyuan.tools.write import get_or_create_doc

    calls: list[tuple[str, dict]] = []

    async def mock_call(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        if endpoint == "/api/query/sql":
            return [{"id": "existing-id"}]
        return None

    mock_sy.call = mock_call
    result = await get_or_create_doc(notebook="nb1", path="/Existing")
    assert result.block_id == "existing-id"
    assert result.was_created is False
    assert result.was_updated is False
    # No createDocWithMd call should have been made.
    assert "/api/filetree/createDocWithMd" not in [c[0] for c in calls]


@pytest.mark.asyncio
async def test_get_or_create_doc_updates_existing(mock_sy):
    """get_or_create_doc updates content when update_if_exists=True."""
    from mcp_siyuan.tools.write import get_or_create_doc

    calls: list[tuple[str, dict]] = []

    async def mock_call(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        if endpoint == "/api/query/sql":
            return [{"id": "existing-id"}]
        return None

    mock_sy.call = mock_call
    result = await get_or_create_doc(
        notebook="nb1",
        path="/Existing",
        markdown="# Updated content",
        update_if_exists=True,
    )
    assert result.was_created is False
    assert result.was_updated is True
    update_call = [c for c in calls if c[0] == "/api/block/updateBlock"]
    assert update_call and update_call[0][1]["data"] == "# Updated content"


@pytest.mark.asyncio
async def test_get_or_create_doc_rejects_unsafe_path(mock_sy):
    """get_or_create_doc rejects SQL-injection characters in path."""
    from mcp_siyuan.tools.write import get_or_create_doc

    with pytest.raises(ValueError, match="unsafe characters"):
        await get_or_create_doc(notebook="nb1", path="/foo'; DROP TABLE blocks; --")


# --- delete_doc (CDI-1092) ---


@pytest.mark.asyncio
async def test_delete_doc_happy_path(mock_sy):
    """delete_doc trusts removeDocByID's success response (no SQL verify)."""
    from mcp_siyuan.tools.write import delete_doc

    # Sequence of calls: getBlockInfo (exists), SQL lookup (type=d row),
    # removeDocByID (None). No SQL verify probe is fired afterwards.
    responses = [
        {"id": "doc1", "type": "d", "rootID": "doc1"},  # getBlockInfo
        [{"id": "doc1", "type": "d", "box": "nb1", "path": "/foo.sy"}],  # SQL lookup
        None,  # removeDocByID
    ]
    calls: list[tuple[str, dict]] = []

    async def mock_call(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return responses.pop(0)

    mock_sy.call = mock_call
    result = await delete_doc(id="doc1")
    assert result["ok"] is True
    assert result["deleted_id"] == "doc1"
    assert result["already_absent"] is False
    # removeDocByID must have been called with the id.
    endpoints = [c[0] for c in calls]
    assert "/api/filetree/removeDocByID" in endpoints


@pytest.mark.asyncio
async def test_delete_doc_no_sql_verify_after_remove(mock_sy):
    """delete_doc must NOT fire a SQL verify probe after removeDocByID (CDI-1092)."""
    from mcp_siyuan.tools.write import delete_doc

    responses = [
        {"id": "doc1", "type": "d", "rootID": "doc1"},  # getBlockInfo
        [{"id": "doc1", "type": "d", "box": "nb1", "path": "/foo.sy"}],  # SQL lookup
        None,  # removeDocByID
    ]
    calls: list[tuple[str, dict]] = []

    async def mock_call(endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return responses.pop(0)

    mock_sy.call = mock_call
    result = await delete_doc(id="doc1")
    assert result["ok"] is True

    # Verify call sequence: getBlockInfo, then SQL lookup, then removeDocByID,
    # and NO SQL probe after removeDocByID.
    endpoints = [c[0] for c in calls]
    assert endpoints[-1] == "/api/filetree/removeDocByID", (
        f"removeDocByID must be the LAST call; got sequence: {endpoints}"
    )
    # Specifically, no `SELECT id FROM blocks WHERE id` probe fires after.
    remove_idx = endpoints.index("/api/filetree/removeDocByID")
    after = calls[remove_idx + 1 :]
    sql_probes_after = [
        c for c in after
        if c[0] == "/api/query/sql"
        and "SELECT id FROM blocks WHERE id" in c[1].get("stmt", "")
    ]
    assert sql_probes_after == [], (
        f"No SQL verify probe should fire after removeDocByID; found: {sql_probes_after}"
    )


@pytest.mark.asyncio
async def test_delete_doc_already_absent_on_lookup(mock_sy):
    """delete_doc returns success if getBlockInfo errors (block missing)."""
    from mcp_siyuan.client import SiYuanError
    from mcp_siyuan.tools.write import delete_doc

    mock_sy.call.side_effect = SiYuanError("ID does not exist", code=-1)
    result = await delete_doc(id="missing-doc")
    assert result["ok"] is True
    assert result["already_absent"] is True
    assert result["deleted_id"] == "missing-doc"


@pytest.mark.asyncio
async def test_delete_doc_rejects_non_document(mock_sy):
    """delete_doc raises ValueError when called on a non-document block."""
    from mcp_siyuan.tools.write import delete_doc

    responses = [
        {"id": "p1", "type": "p", "rootID": "doc1"},  # getBlockInfo returns paragraph
        [{"id": "p1", "type": "p"}],  # SQL re-check confirms paragraph
    ]

    async def mock_call(endpoint, **kwargs):
        return responses.pop(0)

    mock_sy.call = mock_call
    with pytest.raises(ValueError, match="not a document"):
        await delete_doc(id="p1")


@pytest.mark.asyncio
async def test_delete_doc_require_empty_refuses_nonempty(mock_sy):
    """delete_doc with require_empty=True refuses docs that still have children."""
    from mcp_siyuan.tools.write import delete_doc

    responses = [
        {"id": "doc1", "type": "d", "rootID": "doc1"},  # getBlockInfo
        [{"id": "doc1", "type": "d"}],  # SQL lookup
        [{"id": "child1", "type": "h", "content": "Heading"}],  # children present
    ]

    async def mock_call(endpoint, **kwargs):
        return responses.pop(0)

    mock_sy.call = mock_call
    with pytest.raises(ValueError, match="still has"):
        await delete_doc(id="doc1", require_empty=True)
