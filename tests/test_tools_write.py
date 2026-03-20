"""Tests for Tier 2 write tools."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_sy():
    with patch("mcp_siyuan.tools.write.sy") as mock:
        mock.call = AsyncMock()
        yield mock


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
    """update_block sends correct payload."""
    from mcp_siyuan.tools.write import siyuan_update_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "update"}]}]
    result = await siyuan_update_block(id="b1", data="updated text")
    mock_sy.call.assert_called_once_with(
        "/api/block/updateBlock",
        id="b1",
        data="updated text",
        dataType="markdown",
    )


@pytest.mark.asyncio
async def test_insert_block_after(mock_sy):
    """insert_block with previous_id inserts after."""
    from mcp_siyuan.tools.write import siyuan_insert_block

    mock_sy.call.return_value = [{"doOperations": [{"action": "insert", "id": "new1"}]}]
    await siyuan_insert_block(data="new paragraph", previous_id="b1")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("previousID") == "b1"


@pytest.mark.asyncio
async def test_insert_block_before(mock_sy):
    """insert_block with next_id inserts before."""
    from mcp_siyuan.tools.write import siyuan_insert_block

    mock_sy.call.return_value = {"ok": True}
    await siyuan_insert_block(data="before this", next_id="b2")
    call_kwargs = mock_sy.call.call_args
    assert call_kwargs.kwargs.get("nextID") == "b2"


@pytest.mark.asyncio
async def test_insert_block_as_child(mock_sy):
    """insert_block with parent_id inserts as child."""
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
