"""Tier 2 — Write tools for SiYuan."""

from __future__ import annotations

from typing import Any, Literal

from mcp_siyuan.client import sy


def _wrap_result(result: Any) -> dict[str, Any]:
    """Normalise SiYuan write responses to always return a dict."""
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        return {"ok": True, "transactions": result}
    return {"ok": True}


async def siyuan_create_notebook(name: str) -> dict[str, Any]:
    """Create a new notebook in SiYuan.

    Args:
        name: Name for the new notebook.

    Returns:
        Dict containing the notebook object with its ID.
    """
    data = await sy.call("/api/notebook/createNotebook", name=name)
    return data if isinstance(data, dict) else {"ok": True}


async def siyuan_rename_notebook(notebook: str, name: str) -> dict[str, Any]:
    """Rename an existing notebook.

    Args:
        notebook: Notebook ID to rename.
        name: New name for the notebook.
    """
    result = await sy.call(
        "/api/notebook/renameNotebook",
        notebook=notebook,
        name=name,
    )
    return _wrap_result(result)


async def siyuan_remove_notebook(notebook: str) -> dict[str, Any]:
    """Remove a notebook and all its documents.

    This permanently removes the notebook. Use with caution — deletion cannot
    be undone via the API (only via SiYuan's in-app undo).

    Args:
        notebook: Notebook ID to remove.
    """
    result = await sy.call(
        "/api/notebook/removeNotebook",
        notebook=notebook,
    )
    return _wrap_result(result)


async def siyuan_create_document(
    notebook: str, path: str, markdown: str = ""
) -> str:
    """Create a new document in a SiYuan notebook.

    Use siyuan_list_notebooks first to get notebook IDs.
    Only create documents in notebooks with closed=false.

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
    return _wrap_result(result)


async def siyuan_insert_block(
    data: str,
    position: Literal["after", "before", "child"] = "after",
    anchor_id: str = "",
    data_type: Literal["markdown", "dom"] = "markdown",
    # Keep old params for backwards compat but hide from new callers
    previous_id: str = "",
    next_id: str = "",
    parent_id: str = "",
) -> dict[str, Any]:
    """Insert a new block relative to an anchor block.

    Args:
        data: Block content (markdown or DOM).
        position: Where to insert — 'after' (insert after anchor_id),
                  'before' (insert before anchor_id), or 'child' (append as child).
        anchor_id: The block ID to position relative to. Required.
        data_type: Content format — 'markdown' (default) or 'dom'.
    """
    payload: dict[str, Any] = {"data": data, "dataType": data_type}

    # New interface: position + anchor_id
    if anchor_id:
        if position == "before":
            payload["nextID"] = anchor_id
        elif position == "child":
            payload["parentID"] = anchor_id
        else:  # "after"
            payload["previousID"] = anchor_id
    else:
        # Legacy interface fallback
        if next_id:
            payload["nextID"] = next_id
        if previous_id:
            payload["previousID"] = previous_id
        if parent_id:
            payload["parentID"] = parent_id

    result = await sy.call("/api/block/insertBlock", **payload)
    return _wrap_result(result)


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
    return _wrap_result(result)


async def siyuan_delete_block(id: str) -> dict[str, Any]:
    """Delete a block by ID.

    This permanently removes the block. Use with caution — deletion cannot
    be undone via the API (only via SiYuan's in-app undo).

    Args:
        id: The block ID to delete.
    """
    result = await sy.call("/api/block/deleteBlock", id=id)
    return _wrap_result(result)


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


async def siyuan_move_doc(from_ids: list[str], to_id: str) -> dict[str, Any]:
    """Move one or more documents to a new parent document or notebook.

    Args:
        from_ids: List of document IDs to move.
        to_id: Target parent document ID or notebook ID.
    """
    result = await sy.call(
        "/api/filetree/moveDocsByID",
        fromIDs=from_ids,
        toID=to_id,
    )
    return _wrap_result(result)


async def siyuan_rename_doc(id: str, title: str) -> dict[str, Any]:
    """Rename a document without moving it.

    Args:
        id: The document ID to rename.
        title: New title for the document.
    """
    result = await sy.call(
        "/api/filetree/renameDocByID",
        id=id,
        title=title,
    )
    return _wrap_result(result)


async def siyuan_move_block(
    id: str, parent_id: str = "", previous_id: str = ""
) -> dict[str, Any]:
    """Move a block to a new position.

    At least one of parent_id or previous_id must be provided.
    If both are given, previous_id takes precedence (SiYuan API behaviour).

    Args:
        id: The block ID to move.
        parent_id: Target parent block ID — makes the block a child of this parent.
        previous_id: Place the block after this sibling block.
    """
    if not parent_id and not previous_id:
        raise ValueError("At least one of parent_id or previous_id is required.")
    result = await sy.call(
        "/api/block/moveBlock",
        id=id,
        parentID=parent_id,
        previousID=previous_id,
    )
    return _wrap_result(result)


async def siyuan_daily_note(notebook: str = "") -> str:
    """Create or open today's daily note in a notebook.

    Args:
        notebook: Notebook ID. If empty, uses the first open notebook.

    Returns:
        The document ID of today's daily note.
    """
    if not notebook:
        nb_data = await sy.call("/api/notebook/lsNotebooks")
        notebooks = nb_data.get("notebooks", []) if nb_data else []
        open_nbs = [nb for nb in notebooks if not nb.get("closed", False)]
        if not open_nbs:
            raise ValueError("No open notebooks found. Provide a notebook ID.")
        notebook = open_nbs[0]["id"]

    data = await sy.call(
        "/api/filetree/createDailyNote",
        notebook=notebook,
    )
    return data if isinstance(data, str) else str(data)
