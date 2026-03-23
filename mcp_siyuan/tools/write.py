"""Tier 2 — Write tools for SiYuan."""

from __future__ import annotations

from typing import Any, Literal

from mcp_siyuan.client import sy


async def siyuan_create_document(
    notebook: str, path: str, markdown: str = ""
) -> str:
    """Create a new document in a SiYuan notebook.

    Args:
        notebook: Notebook ID (e.g. '20210817205410-2kvfpfn').
        path: Document path within the notebook (e.g. '/foo/bar').
        markdown: Optional GFM markdown content for the document.

    Returns:
        The ID of the newly created document.
    """
    data = await sy.call(
        "/api/filetree/createDocWithMd",
        notebook=notebook,
        path=path,
        markdown=markdown,
    )
    return data if isinstance(data, str) else str(data)


async def siyuan_update_block(
    id: str, data: str, data_type: Literal["markdown", "dom"] = "markdown"
) -> dict[str, Any]:
    """Update an existing block's content.

    Args:
        id: The block ID to update.
        data: New content for the block.
        data_type: Content format — 'markdown' (default) or 'dom'.
    """
    result = await sy.call(
        "/api/block/updateBlock",
        id=id,
        data=data,
        dataType=data_type,
    )
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        return {"ok": True, "transactions": result}
    return {"ok": True}


async def siyuan_insert_block(
    data: str,
    data_type: Literal["markdown", "dom"] = "markdown",
    previous_id: str = "",
    next_id: str = "",
    parent_id: str = "",
) -> dict[str, Any]:
    """Insert a new block at a specified position.

    Provide exactly one anchor: previous_id (insert after), next_id (insert before),
    or parent_id (insert as child). Priority: next_id > previous_id > parent_id.

    Args:
        data: Block content.
        data_type: Content format — 'markdown' (default) or 'dom'.
        previous_id: Insert after this block.
        next_id: Insert before this block.
        parent_id: Insert as child of this block.
    """
    payload: dict[str, Any] = {"data": data, "dataType": data_type}
    if next_id:
        payload["nextID"] = next_id
    if previous_id:
        payload["previousID"] = previous_id
    if parent_id:
        payload["parentID"] = parent_id

    result = await sy.call("/api/block/insertBlock", **payload)
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        return {"ok": True, "transactions": result}
    return {"ok": True}


async def siyuan_append_block(
    parent_id: str, data: str, data_type: Literal["markdown", "dom"] = "markdown"
) -> dict[str, Any]:
    """Append content to the end of a document or container block.

    Args:
        parent_id: The document or container block ID to append to.
        data: Content to append.
        data_type: Content format — 'markdown' (default) or 'dom'.
    """
    result = await sy.call(
        "/api/block/appendBlock",
        data=data,
        dataType=data_type,
        parentID=parent_id,
    )
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        return {"ok": True, "transactions": result}
    return {"ok": True}


async def siyuan_set_block_attrs(id: str, attrs: dict[str, str]) -> dict[str, Any]:
    """Set attributes on a block.

    Args:
        id: The block ID.
        attrs: Dictionary of attribute key-value pairs (e.g. {'custom-status': 'reviewed'}).
    """
    result = await sy.call(
        "/api/attr/setBlockAttrs",
        id=id,
        attrs=attrs,
    )
    return result if isinstance(result, dict) else {"ok": True}


async def siyuan_daily_note(notebook: str) -> str:
    """Create or open today's daily note in a notebook.

    Args:
        notebook: Notebook ID to create the daily note in.

    Returns:
        The document ID of today's daily note.
    """
    data = await sy.call(
        "/api/filetree/createDailyNote",
        notebook=notebook,
    )
    return data if isinstance(data, str) else str(data)
