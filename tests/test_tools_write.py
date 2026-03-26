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
    from mcp_siyuan.tools.write import siyuan_create_notebook

    mock_sy.call.return_value = {
        "notebook": {"id": "20260326100000-abc1234", "name": "Test Notebook"}
    }
    result = await siyuan_create_notebook(name="Test Notebook")
    assert result["notebook"]["id"] == "20260326100000-abc1234"
    mock_sy.call.assert_called_once_with(
        "/api/notebook/createNotebook",
        name="Test Notebook",
    )


@pytest.mark.asyncio
async def test_create_notebook_null_response(mock_sy):
    """create_notebook handles null data response."""
    from mcp_siyuan.tools.write import siyuan_create_notebook

    mock_sy.call.return_value = None
    result = await siyuan_create_notebook(name="Another Notebook")
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_create_document(mock_sy):
    """create_document returns new doc ID."""
    from mcp_siyuan.tools.write import siyuan_create_document

    mock_sy.call.return_value = "20210914223645-oj2vnx2"
    result = await siyuan_create_document(
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
    from mcp_siyuan.tools.write import siyuan_create_document

    mock_sy.call.return_value = "doc-id-123"
    result = await siyuan_create_document(notebook="nb1", path="/empty")
    assert result == "doc-id-123"


@pytest.mark.asyncio
async def test_update_block(mock_sy):
    """update_block sends correct payload and wraps list result."""
    from mcp_siyuan.tools.write import siyuan_update_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "update"}]}]
    result = await siyuan_update_block(id="b1", data="updated text")
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
    from mcp_siyuan.tools.write import siyuan_insert_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "insert", "id": "new1"}]}]
    await siyuan_insert_block(data="new paragraph", position="after", anchor_id="b1")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("previousID") == "b1"


@pytest.mark.asyncio
async def test_insert_block_before_new_interface(mock_sy):
    """insert_block with position='before' and anchor_id."""
    from mcp_siyuan.tools.write import siyuan_insert_block

    mock_sy.call.return_value = {"ok": True}
    await siyuan_insert_block(data="before this", position="before", anchor_id="b2")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("nextID") == "b2"


@pytest.mark.asyncio
async def test_insert_block_child_new_interface(mock_sy):
    """insert_block with position='child' and anchor_id."""
    from mcp_siyuan.tools.write import siyuan_insert_block

    mock_sy.call.return_value = {"ok": True}
    await siyuan_insert_block(data="child block", position="child", anchor_id="doc1")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("parentID") == "doc1"


@pytest.mark.asyncio
async def test_insert_block_legacy_previous_id(mock_sy):
    """insert_block still works with legacy previous_id param."""
    from mcp_siyuan.tools.write import siyuan_insert_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "insert", "id": "new1"}]}]
    await siyuan_insert_block(data="new paragraph", previous_id="b1")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("previousID") == "b1"


@pytest.mark.asyncio
async def test_insert_block_legacy_next_id(mock_sy):
    """insert_block still works with legacy next_id param."""
    from mcp_siyuan.tools.write import siyuan_insert_block

    mock_sy.call.return_value = {"ok": True}
    await siyuan_insert_block(data="before this", next_id="b2")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("nextID") == "b2"


@pytest.mark.asyncio
async def test_insert_block_legacy_parent_id(mock_sy):
    """insert_block still works with legacy parent_id param."""
    from mcp_siyuan.tools.write import siyuan_insert_block

    mock_sy.call.return_value = {"ok": True}
    await siyuan_insert_block(data="child block", parent_id="doc1")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("parentID") == "doc1"


@pytest.mark.asyncio
async def test_append_block(mock_sy):
    """append_block sends parent_id correctly."""
    from mcp_siyuan.tools.write import siyuan_append_block

    mock_sy.call.return_value = {"ok": True}
    await siyuan_append_block(parent_id="doc1", data="appended text")
    mock_sy.call.assert_called_once_with(
        "/api/block/appendBlock",
        data="appended text",
        dataType="markdown",
        parentID="doc1",
    )


@pytest.mark.asyncio
async def test_delete_block(mock_sy):
    """delete_block sends correct payload."""
    from mcp_siyuan.tools.write import siyuan_delete_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "delete"}]}]
    result = await siyuan_delete_block(id="b1")
    assert result["ok"] is True
    mock_sy.call.assert_called_once_with("/api/block/deleteBlock", id="b1")


@pytest.mark.asyncio
async def test_set_block_attrs(mock_sy):
    """set_block_attrs sends attrs dict."""
    from mcp_siyuan.tools.write import siyuan_set_block_attrs

    mock_sy.call.return_value = None
    await siyuan_set_block_attrs(id="b1", attrs={"custom-status": "done"})
    mock_sy.call.assert_called_once_with(
        "/api/attr/setBlockAttrs",
        id="b1",
        attrs={"custom-status": "done"},
    )


@pytest.mark.asyncio
async def test_move_doc_single(mock_sy):
    """move_doc sends single doc ID to moveDocsByID."""
    from mcp_siyuan.tools.write import siyuan_move_doc

    mock_sy.call.return_value = None
    result = await siyuan_move_doc(from_ids=["doc1"], to_id="notebook1")
    assert result == {"ok": True}
    mock_sy.call.assert_called_once_with(
        "/api/filetree/moveDocsByID",
        fromIDs=["doc1"],
        toID="notebook1",
    )


@pytest.mark.asyncio
async def test_move_doc_multiple(mock_sy):
    """move_doc supports moving multiple documents at once."""
    from mcp_siyuan.tools.write import siyuan_move_doc

    mock_sy.call.return_value = None
    result = await siyuan_move_doc(from_ids=["doc1", "doc2"], to_id="parent-doc")
    assert result == {"ok": True}
    mock_sy.call.assert_called_once_with(
        "/api/filetree/moveDocsByID",
        fromIDs=["doc1", "doc2"],
        toID="parent-doc",
    )


@pytest.mark.asyncio
async def test_rename_doc(mock_sy):
    """rename_doc sends id and title to renameDocByID."""
    from mcp_siyuan.tools.write import siyuan_rename_doc

    mock_sy.call.return_value = None
    result = await siyuan_rename_doc(id="doc1", title="New Title")
    assert result == {"ok": True}
    mock_sy.call.assert_called_once_with(
        "/api/filetree/renameDocByID",
        id="doc1",
        title="New Title",
    )


@pytest.mark.asyncio
async def test_move_block_previous(mock_sy):
    """move_block with previous_id sends correct payload."""
    from mcp_siyuan.tools.write import siyuan_move_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "move"}]}]
    result = await siyuan_move_block(id="block1", previous_id="sibling1")
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
    from mcp_siyuan.tools.write import siyuan_move_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "move"}]}]
    result = await siyuan_move_block(id="block1", parent_id="parent1")
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
    from mcp_siyuan.tools.write import siyuan_move_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "move"}]}]
    result = await siyuan_move_block(
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
    from mcp_siyuan.tools.write import siyuan_move_block

    with pytest.raises(ValueError, match="At least one of"):
        await siyuan_move_block(id="block1")


@pytest.mark.asyncio
async def test_daily_note(mock_sy):
    """daily_note returns document ID."""
    from mcp_siyuan.tools.write import siyuan_daily_note

    mock_sy.call.return_value = "daily-note-id"
    result = await siyuan_daily_note(notebook="nb1")
    assert result == "daily-note-id"
    mock_sy.call.assert_called_once_with(
        "/api/filetree/createDailyNote",
        notebook="nb1",
    )


@pytest.mark.asyncio
async def test_daily_note_auto_notebook(mock_sy):
    """daily_note picks first open notebook when none specified."""
    from mcp_siyuan.tools.write import siyuan_daily_note

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
    result = await siyuan_daily_note()
    assert result == "daily-auto-id"
