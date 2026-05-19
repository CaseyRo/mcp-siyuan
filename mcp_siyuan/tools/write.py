"""Tier 2 — Write tools for SiYuan."""

from __future__ import annotations

import logging
from typing import Any, Literal

from mcp_siyuan.client import sy
from mcp_siyuan.idempotency import cache as idempotency_cache

logger = logging.getLogger(__name__)


def _wrap_result(result: Any) -> dict[str, Any]:
    """Normalise SiYuan write responses to always return a dict."""
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        return {"ok": True, "transactions": result}
    return {"ok": True}


async def create_notebook(name: str) -> dict[str, Any]:
    """[notes] Create a new notebook in SiYuan.

    Args:
        name: Name for the new notebook.

    Returns:
        Dict containing the notebook object with its ID.
    """
    data = await sy.call("/api/notebook/createNotebook", name=name)
    return data if isinstance(data, dict) else {"ok": True}


async def rename_notebook(notebook: str, name: str) -> dict[str, Any]:
    """[notes] Rename an existing notebook.

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


async def remove_notebook(notebook: str) -> dict[str, Any]:
    """[notes] Remove a notebook and all its documents.

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


async def create_document(
    notebook: str,
    path: str,
    markdown: str = "",
    idempotency_key: str | None = None,
) -> str:
    """[notes] Create a new document in a SiYuan notebook.

    Use list_notebooks first to get notebook IDs.
    Only create documents in notebooks with closed=false.

    Args:
        notebook: Notebook ID (e.g. '20210817205410-2kvfpfn').
        path: Document path within the notebook (e.g. '/foo/bar').
        markdown: Optional GFM markdown content for the document.
        idempotency_key: Optional client-supplied key. If provided, replaying
            the same key within SIYUAN_IDEMPOTENCY_TTL_SECONDS returns the
            prior result without a new kernel call. Failures are NOT cached.
            Allowed: ^[A-Za-z0-9_\\-:.]+$, length 1..128.

    Returns:
        The ID of the newly created document.
    """

    async def _call() -> str:
        data = await sy.call(
            "/api/filetree/createDocWithMd",
            notebook=notebook,
            path=path,
            markdown=markdown,
        )
        return data if isinstance(data, str) else str(data)

    return await idempotency_cache.with_idempotency(
        "create_document", idempotency_key, _call
    )


async def update_block(
    id: str,
    data: str,
    data_type: Literal["markdown", "dom"] = "markdown",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """[notes] Update an existing block's content.

    Args:
        id: The block ID to update.
        data: New content for the block.
        data_type: Content format — 'markdown' (default) or 'dom'.
        idempotency_key: Optional replay-cache key (see create_document).
    """

    async def _call() -> dict[str, Any]:
        result = await sy.call(
            "/api/block/updateBlock",
            id=id,
            data=data,
            dataType=data_type,
        )
        return _wrap_result(result)

    return await idempotency_cache.with_idempotency(
        "update_block", idempotency_key, _call
    )


async def insert_block(
    data: str,
    position: Literal["after", "before", "child"] = "after",
    anchor_id: str = "",
    data_type: Literal["markdown", "dom"] = "markdown",
    # Keep old params for backwards compat but hide from new callers
    previous_id: str = "",
    next_id: str = "",
    parent_id: str = "",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """[notes] Insert a new block relative to an anchor block.

    Args:
        data: Block content (markdown or DOM).
        position: Where to insert — 'after' (insert after anchor_id),
                  'before' (insert before anchor_id), or 'child' (append as child).
        anchor_id: The block ID to position relative to. Required.
        data_type: Content format — 'markdown' (default) or 'dom'.
        idempotency_key: Optional replay-cache key (see create_document).
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

    async def _call() -> dict[str, Any]:
        result = await sy.call("/api/block/insertBlock", **payload)
        return _wrap_result(result)

    return await idempotency_cache.with_idempotency(
        "insert_block", idempotency_key, _call
    )


async def append_block(
    parent_id: str,
    data: str,
    data_type: Literal["markdown", "dom"] = "markdown",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """[notes] Append content to the end of a document or container block.

    Args:
        parent_id: The document or container block ID to append to.
        data: Content to append.
        data_type: Content format — 'markdown' (default) or 'dom'.
        idempotency_key: Optional replay-cache key (see create_document).
    """

    async def _call() -> dict[str, Any]:
        result = await sy.call(
            "/api/block/appendBlock",
            data=data,
            dataType=data_type,
            parentID=parent_id,
        )
        return _wrap_result(result)

    return await idempotency_cache.with_idempotency(
        "append_block", idempotency_key, _call
    )


async def delete_block(
    id: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """[notes] Delete a block by ID.

    This permanently removes the block. Use with caution — deletion cannot
    be undone via the API (only via SiYuan's in-app undo).

    Idempotent: re-deleting an already-missing block returns success rather
    than an error, so callers can safely retry without side effects.

    Args:
        id: The block ID to delete.
        idempotency_key: Optional replay-cache key (see create_document).
            Replaying the same key within SIYUAN_IDEMPOTENCY_TTL_SECONDS
            returns the prior result without a new kernel call.
    """
    from mcp_siyuan.client import SiYuanError

    async def _call() -> dict[str, Any]:
        try:
            result = await sy.call("/api/block/deleteBlock", id=id)
            return _wrap_result(result)
        except SiYuanError as exc:
            # SiYuan returns a non-zero code when the block does not exist.
            # Treat this as a successful no-op so deletes are safe to replay.
            logger.info(
                "delete_block: block %s already absent (code=%s), returning success",
                id,
                exc.code,
            )
            return {"ok": True, "already_absent": True}

    return await idempotency_cache.with_idempotency(
        "delete_block", idempotency_key, _call
    )


async def set_block_attrs(
    id: str,
    attrs: dict[str, str],
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """[notes] Set attributes on a block.

    Args:
        id: The block ID.
        attrs: Dictionary of attribute key-value pairs (e.g. {'custom-status': 'reviewed'}).
        idempotency_key: Optional replay-cache key (see create_document).
    """

    async def _call() -> dict[str, Any]:
        result = await sy.call(
            "/api/attr/setBlockAttrs",
            id=id,
            attrs=attrs,
        )
        return result if isinstance(result, dict) else {"ok": True}

    return await idempotency_cache.with_idempotency(
        "set_block_attrs", idempotency_key, _call
    )


async def move_doc(from_ids: list[str], to_id: str) -> dict[str, Any]:
    """[notes] Move one or more documents to a new parent document or notebook.

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


async def rename_doc(id: str, title: str) -> dict[str, Any]:
    """[notes] Rename a document without moving it.

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


async def move_block(
    id: str, parent_id: str = "", previous_id: str = ""
) -> dict[str, Any]:
    """[notes] Move a block to a new position.

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


async def delete_doc(
    id: str,
    require_empty: bool = False,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """[notes] Delete a document by its block ID.

    Unlike ``delete_block`` (which silently no-ops on type='d' document blocks
    because it operates on the inline empty paragraph inside the doc), this
    tool wraps SiYuan's ``/api/filetree/removeDocByID`` and actually removes
    the document container.

    After removal, the doc is gone from both the SQL view and the SiYuan UI.
    Already-absent documents return success so callers can safely retry.

    Args:
        id: The document block ID to delete (type='d').
        require_empty: If True, refuse to delete documents that still have
            child blocks beyond an empty paragraph, to prevent accidental
            tree wipes. Defaults to False.
        idempotency_key: Optional replay-cache key (see create_document).

    Returns:
        ``{"ok": True, "deleted_id": <id>, "already_absent": <bool>}``.

    Raises:
        ValueError: If ``id`` does not refer to a document-type block, or
            ``require_empty=True`` and the doc still has children.
    """
    from mcp_siyuan.client import SiYuanError

    async def _call() -> dict[str, Any]:
        # 1. Verify the block exists and is a document.
        try:
            info = await sy.call("/api/block/getBlockInfo", id=id)
        except SiYuanError as exc:
            # Treat missing-block on lookup as already-absent — idempotent.
            logger.info(
                "delete_doc: block %s lookup failed (code=%s), assuming absent",
                id,
                exc.code,
            )
            return {"ok": True, "deleted_id": id, "already_absent": True}
        if not info:
            return {"ok": True, "deleted_id": id, "already_absent": True}

        block_type = info.get("type") or info.get("type_", "")
        # getBlockInfo for documents typically returns rootID == id and the
        # field may be absent; verify via SQL.
        if block_type and block_type != "d":
            # Fall back to SQL check — getBlockInfo sometimes lacks `type`.
            sql = await sy.call(
                "/api/query/sql",
                stmt=f"SELECT id, type, box, path FROM blocks WHERE id = '{id}' LIMIT 1",
            )
            row = sql[0] if isinstance(sql, list) and sql else None
            if row and row.get("type") != "d":
                raise ValueError(
                    f"Block {id} is type='{row.get('type')}', not a document. "
                    "Use siyuan_delete_block for non-document blocks."
                )

        # 2. Look up notebook + path from SQL (removeDocByID accepts ID
        #    directly but we double-check existence and grab path metadata).
        sql = await sy.call(
            "/api/query/sql",
            stmt=f"SELECT id, type, box, path FROM blocks WHERE id = '{id}' AND type = 'd' LIMIT 1",
        )
        row = sql[0] if isinstance(sql, list) and sql else None
        if not row:
            return {"ok": True, "deleted_id": id, "already_absent": True}

        # 3. Optional safety: refuse to delete non-empty docs.
        if require_empty:
            child_rows = await sy.call(
                "/api/query/sql",
                stmt=(
                    f"SELECT id, type, content FROM blocks WHERE parent_id = '{id}' "
                    f"AND NOT (type = 'p' AND content = '') LIMIT 2"
                ),
            )
            if isinstance(child_rows, list) and child_rows:
                raise ValueError(
                    f"Document {id} still has {len(child_rows)} child block(s); "
                    "pass require_empty=False to delete anyway."
                )

        # 4. Remove via the filetree endpoint.
        try:
            result = await sy.call("/api/filetree/removeDocByID", id=id)
        except SiYuanError as exc:
            logger.info(
                "delete_doc: removeDocByID failed (code=%s); verifying absence",
                exc.code,
            )
            result = None

        # 5. Verify the doc is gone via SQL.
        verify = await sy.call(
            "/api/query/sql",
            stmt=f"SELECT id FROM blocks WHERE id = '{id}' LIMIT 1",
        )
        still_present = bool(isinstance(verify, list) and verify)
        if still_present:
            raise SiYuanError(
                f"removeDocByID returned success but doc {id} is still queryable. "
                "Try again or remove manually in the SiYuan UI."
            )
        return {
            "ok": True,
            "deleted_id": id,
            "already_absent": False,
            "result": result if isinstance(result, (dict, list)) else None,
        }

    return await idempotency_cache.with_idempotency(
        "delete_doc", idempotency_key, _call
    )


async def daily_note(notebook: str = "") -> str:
    """[notes] Create or open today's daily note in a notebook.

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
