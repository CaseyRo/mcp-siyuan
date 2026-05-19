"""Tier 2 — Write tools for SiYuan."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any, Literal

from pydantic import Field

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


def _normalise_heading(text: str) -> str:
    """Lowercase + collapse internal whitespace for tolerant heading match."""
    return " ".join(text.split()).strip().lower()


def _heading_level(subtype: str) -> int:
    """Return numeric heading level from a SiYuan subtype like 'h2'."""
    if not subtype or len(subtype) < 2 or subtype[0].lower() != "h":
        return 99
    try:
        return int(subtype[1:])
    except ValueError:
        return 99


async def _find_section(
    doc_id: str, section_heading: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    """Locate a heading by name within a document.

    Returns (heading_row, section_blocks, all_headings) where
    ``section_blocks`` is the list of blocks under ``heading_row`` up to (but
    not including) the next heading at the same or higher level. Match is
    case-insensitive and whitespace-tolerant.
    """
    safe_doc = doc_id
    if any(c in doc_id for c in ("'", '"', ";", "\n")):
        raise ValueError("doc_id contains unsafe characters")

    # 1. Fetch all blocks at the document level, ordered by sort, so we can
    #    determine section boundaries by traversal.
    rows = await sy.call(
        "/api/query/sql",
        stmt=(
            f"SELECT id, type, subtype, content, sort FROM blocks "
            f"WHERE root_id = '{safe_doc}' AND parent_id = '{safe_doc}' "
            f"ORDER BY sort ASC LIMIT 1000"
        ),
    )
    blocks = rows if isinstance(rows, list) else []
    headings = [b for b in blocks if b.get("type") == "h"]

    target = _normalise_heading(section_heading)
    heading_row: dict[str, Any] | None = None
    for h in headings:
        if _normalise_heading(h.get("content") or "") == target:
            heading_row = h
            break
    if heading_row is None:
        return None, [], headings

    # 2. Walk forward from the heading; stop at the next heading at same or
    #    higher level (numerically lower or equal subtype).
    h_level = _heading_level(heading_row.get("subtype") or "")
    start_sort = heading_row.get("sort", 0)
    section_blocks: list[dict[str, Any]] = []
    for b in blocks:
        if b.get("sort", 0) <= start_sort or b.get("id") == heading_row.get("id"):
            continue
        if b.get("type") == "h" and _heading_level(b.get("subtype") or "") <= h_level:
            break
        section_blocks.append(b)
    return heading_row, section_blocks, headings


async def upsert_section(
    doc_id: str,
    section_heading: str,
    markdown: str,
    heading_level: Annotated[int, Field(ge=1, le=6)] = 2,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """[notes] Replace (or create) a named section's content in a document.

    Finds the heading whose text matches ``section_heading`` (case-insensitive,
    whitespace-tolerant). Deletes every block between that heading and the
    next heading at the same or higher level, then inserts ``markdown`` in
    place. The heading itself is preserved.

    If no matching heading is found, appends a new ``# ... heading_level``
    heading at the end of the document followed by ``markdown``.

    Args:
        doc_id: The document block ID.
        section_heading: Heading text to match (case-insensitive,
            whitespace-tolerant).
        markdown: Replacement content for the section.
        heading_level: Level used when creating a brand-new section (1..6,
            default 2 → ``## Heading``).
        idempotency_key: Optional replay-cache key (see create_document).

    Returns:
        ``{"ok": True, "action": "replaced" | "created", "heading_id": <id>}``.
    """
    if not 1 <= int(heading_level) <= 6:
        raise ValueError("heading_level must be between 1 and 6")

    async def _call() -> dict[str, Any]:
        heading_row, section_blocks, _ = await _find_section(
            doc_id, section_heading
        )
        if heading_row is None:
            # Append a new heading + body at the end of the doc.
            hashes = "#" * int(heading_level)
            payload = f"{hashes} {section_heading}\n\n{markdown}".rstrip() + "\n"
            await sy.call(
                "/api/block/appendBlock",
                data=payload,
                dataType="markdown",
                parentID=doc_id,
            )
            return {"ok": True, "action": "created", "heading_id": None}

        # Replace section content: delete current section blocks, then insert
        # markdown after the heading. Delete from last to first to keep sort
        # stable.
        for block in reversed(section_blocks):
            block_id = block.get("id")
            if not block_id:
                continue
            try:
                await sy.call("/api/block/deleteBlock", id=block_id)
            except Exception:
                # Best-effort delete — surfacing a partial failure here would
                # leave the section half-replaced. Continue.
                logger.warning(
                    "upsert_section: failed to delete block %s", block_id
                )

        if markdown.strip():
            await sy.call(
                "/api/block/insertBlock",
                data=markdown,
                dataType="markdown",
                previousID=heading_row["id"],
            )
        return {
            "ok": True,
            "action": "replaced",
            "heading_id": heading_row.get("id"),
        }

    return await idempotency_cache.with_idempotency(
        "upsert_section", idempotency_key, _call
    )


async def append_to_section(
    doc_id: str,
    section_heading: str,
    markdown: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """[notes] Append block(s) at the end of a named section.

    Finds the heading whose text matches ``section_heading`` (case-insensitive,
    whitespace-tolerant), then inserts ``markdown`` after the last block in
    that section but before the next heading at the same or higher level.

    Unlike ``upsert_section``, this errors when the heading does not exist —
    use ``upsert_section`` for create-or-update semantics.

    Args:
        doc_id: The document block ID.
        section_heading: Heading text to match.
        markdown: Markdown content to append (may contain multiple blocks).
        idempotency_key: Optional replay-cache key (see create_document).

    Returns:
        ``{"ok": True, "heading_id": <id>, "anchor_id": <last-block-id>}``.

    Raises:
        ValueError: If no heading with the given name is found.
    """

    async def _call() -> dict[str, Any]:
        heading_row, section_blocks, _ = await _find_section(
            doc_id, section_heading
        )
        if heading_row is None:
            raise ValueError(
                f"Section heading '{section_heading}' not found in doc {doc_id}. "
                "Use upsert_section to create it."
            )
        # Anchor: the last block in the section, or the heading itself if empty.
        anchor_id = (
            section_blocks[-1]["id"] if section_blocks else heading_row["id"]
        )
        await sy.call(
            "/api/block/insertBlock",
            data=markdown,
            dataType="markdown",
            previousID=anchor_id,
        )
        return {
            "ok": True,
            "heading_id": heading_row.get("id"),
            "anchor_id": anchor_id,
        }

    return await idempotency_cache.with_idempotency(
        "append_to_section", idempotency_key, _call
    )


async def get_or_create_doc(
    notebook: str,
    path: str,
    markdown: str = "",
    update_if_exists: bool = False,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """[notes] Idempotent upsert of a document by ``notebook`` + ``path``.

    If a document already exists at the given path, return its block ID
    without creating a duplicate. If ``update_if_exists=True``, replace its
    content with ``markdown``. If no document exists, create one and return
    the new block ID.

    Path matching uses SiYuan's canonical ``hpath`` format — see
    ``siyuan_doc_exists`` for details on path normalisation.

    Args:
        notebook: Notebook ID to look in / create within.
        path: Document hpath inside the notebook. A path without a leading
            slash is treated as ``/<path>``.
        markdown: Content for the doc. Used on creation, and on update when
            ``update_if_exists=True``.
        update_if_exists: When True and the doc already exists, replace its
            content via ``updateBlock``. Defaults to False (find-only).
        idempotency_key: Optional replay-cache key (see create_document).

    Returns:
        ``{"block_id": <id>, "was_created": <bool>, "was_updated": <bool>,
        "hpath": <path>}``.
    """
    hpath = path if path.startswith("/") else f"/{path}"
    # Reject characters that could break out of the SQL string literal.
    if any(c in (notebook + hpath) for c in ("'", '"', ";", "\n")):
        raise ValueError("notebook/path contain unsafe characters")

    async def _call() -> dict[str, Any]:
        lookup = await sy.call(
            "/api/query/sql",
            stmt=(
                f"SELECT id FROM blocks WHERE type = 'd' AND box = '{notebook}' "
                f"AND hpath = '{hpath}' LIMIT 1"
            ),
        )
        rows = lookup if isinstance(lookup, list) else []
        if rows:
            block_id = rows[0].get("id")
            was_updated = False
            if update_if_exists and markdown:
                await sy.call(
                    "/api/block/updateBlock",
                    id=block_id,
                    data=markdown,
                    dataType="markdown",
                )
                was_updated = True
            return {
                "block_id": block_id,
                "was_created": False,
                "was_updated": was_updated,
                "hpath": hpath,
            }

        data = await sy.call(
            "/api/filetree/createDocWithMd",
            notebook=notebook,
            path=hpath,
            markdown=markdown,
        )
        new_id = data if isinstance(data, str) else str(data)
        return {
            "block_id": new_id,
            "was_created": True,
            "was_updated": False,
            "hpath": hpath,
        }

    return await idempotency_cache.with_idempotency(
        "get_or_create_doc", idempotency_key, _call
    )


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

        # 5. Verify the doc is gone via SQL. SiYuan's kernel returns success
        #    from removeDocByID before the SQL index is updated, so retry with
        #    short backoff to avoid an index-race false positive (CDI-1092).
        verify_backoffs = (0.05, 0.1, 0.2, 0.4)  # seconds between retries; <1s total
        still_present = True
        for attempt in range(5):
            if attempt > 0:
                await asyncio.sleep(verify_backoffs[attempt - 1])
            verify = await sy.call(
                "/api/query/sql",
                stmt=f"SELECT id FROM blocks WHERE id = '{id}' LIMIT 1",
            )
            still_present = bool(isinstance(verify, list) and verify)
            if not still_present:
                break
        if still_present:
            raise SiYuanError(
                f"removeDocByID returned success but doc {id} is still queryable "
                "after retries. Try again or remove manually in the SiYuan UI."
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


_BULK_MAX = 50


async def bulk_create_documents(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """[notes] Create multiple documents in one call.

    Each item is processed independently — per-item failures do NOT abort
    the batch. Returns a parallel array of per-item results so callers can
    retry only the failures.

    Batch size is capped at 50 items. Pass larger batches in multiple calls.

    Args:
        documents: List of ``{"notebook": str, "path": str, "markdown": str}``
            entries. ``markdown`` is optional and defaults to empty.

    Returns:
        List of ``{"path": str, "block_id": str | None, "status": "ok" | "error",
        "error": str | None}``.
    """
    if not isinstance(documents, list):
        raise TypeError("documents must be a list")
    if len(documents) > _BULK_MAX:
        raise ValueError(
            f"batch size {len(documents)} exceeds limit of {_BULK_MAX}"
        )

    from mcp_siyuan.client import SiYuanError

    results: list[dict[str, Any]] = []
    for item in documents:
        notebook = item.get("notebook", "")
        path = item.get("path", "")
        markdown = item.get("markdown", "")
        if not notebook or not path:
            results.append({
                "path": path,
                "block_id": None,
                "status": "error",
                "error": "notebook and path are required",
            })
            continue
        try:
            data = await sy.call(
                "/api/filetree/createDocWithMd",
                notebook=notebook,
                path=path,
                markdown=markdown,
            )
            new_id = data if isinstance(data, str) else str(data)
            results.append({
                "path": path,
                "block_id": new_id,
                "status": "ok",
                "error": None,
            })
        except (SiYuanError, ValueError) as exc:
            results.append({
                "path": path,
                "block_id": None,
                "status": "error",
                "error": str(exc),
            })
    return results


async def bulk_set_attrs(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """[notes] Set attributes on multiple blocks in one call.

    Each item is processed independently — per-item failures do NOT abort
    the batch. Batch size is capped at 50 items.

    Args:
        items: List of ``{"block_id": str, "attrs": dict[str, str]}`` entries.

    Returns:
        List of ``{"block_id": str, "status": "ok" | "error",
        "error": str | None}``.
    """
    if not isinstance(items, list):
        raise TypeError("items must be a list")
    if len(items) > _BULK_MAX:
        raise ValueError(
            f"batch size {len(items)} exceeds limit of {_BULK_MAX}"
        )

    from mcp_siyuan.client import SiYuanError

    results: list[dict[str, Any]] = []
    for entry in items:
        block_id = entry.get("block_id", "")
        attrs = entry.get("attrs", {})
        if not block_id or not isinstance(attrs, dict):
            results.append({
                "block_id": block_id,
                "status": "error",
                "error": "block_id and attrs (dict) are required",
            })
            continue
        try:
            await sy.call(
                "/api/attr/setBlockAttrs",
                id=block_id,
                attrs=attrs,
            )
            results.append({
                "block_id": block_id,
                "status": "ok",
                "error": None,
            })
        except (SiYuanError, ValueError) as exc:
            results.append({
                "block_id": block_id,
                "status": "error",
                "error": str(exc),
            })
    return results


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
