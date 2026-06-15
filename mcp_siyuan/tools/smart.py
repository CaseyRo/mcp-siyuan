"""High-level, LLM-ergonomic tools for SiYuan."""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from mcp_siyuan.client import sy
from mcp_siyuan.models import (
    Backlink,
    BlockChildren,
    CaptureTaskResult,
    ContextSearchHit,
    DocExistsResult,
    OutlineHeading,
    RecentDoc,
    TaggedBlock,
    TagCount,
    TaskItem,
)

logger = logging.getLogger(__name__)

# --- SQL safety helper ---

_UNSAFE_SQL_RE = re.compile(r"['\";]|--|/\*")


def _sanitize(value: str) -> str:
    """Reject values that could break out of a SQL string literal."""
    if _UNSAFE_SQL_RE.search(value):
        raise ValueError(f"Unsafe characters in SQL parameter: {value!r}")
    return value


async def get_recent_docs(
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
    notebook: str = "",
) -> list[RecentDoc]:
    """[notes] Get recently modified documents, newest first.

    Great for understanding what the user has been working on lately.

    Args:
        limit: Max number of documents to return (default 10, max 50).
        notebook: Optional notebook ID to filter by. Empty = all notebooks.
    """
    where = "WHERE type = 'd'"
    if notebook:
        where += f" AND box = '{_sanitize(notebook)}'"
    stmt = f"SELECT id, content AS title, box, hpath, updated FROM blocks {where} ORDER BY updated DESC LIMIT {limit}"
    data = await sy.call("/api/query/sql", stmt=stmt)
    rows = data if isinstance(data, list) else []
    return [RecentDoc(**row) for row in rows]


async def find_tasks(
    notebook: str = "",
    checked: bool = False,
    days: Annotated[int, Field(ge=1, le=365)] = 7,
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
) -> list[TaskItem]:
    """[notes] Find task/TODO items across SiYuan notes.

    Searches for task list items (checkbox blocks). Perfect for extracting
    TODOs from daily notes for export to task managers.

    Returns each task with its parent document title (doc_title) so you
    don't need a follow-up call to identify which note it belongs to.

    Args:
        notebook: Optional notebook ID to scope the search. Empty = all notebooks.
        checked: If True, return completed tasks. If False (default), return open/unchecked tasks.
        days: Look back this many days (default 7).
        limit: Max results (default 50, max 100).
    """
    subtype_filter = "'t'" if not checked else "'d'"
    where = f"WHERE b.type = 'i' AND b.subtype = {subtype_filter}"
    if notebook:
        where += f" AND b.box = '{_sanitize(notebook)}'"
    where += f" AND b.updated >= strftime('%Y%m%d%H%M%S', datetime('now', '-{days} days'))"

    stmt = (
        f"SELECT b.id, b.content, b.box, b.hpath, b.root_id, b.updated, "
        f"d.content AS doc_title "
        f"FROM blocks b "
        f"LEFT JOIN blocks d ON d.id = b.root_id AND d.type = 'd' "
        f"{where} ORDER BY b.updated DESC LIMIT {limit}"
    )
    data = await sy.call("/api/query/sql", stmt=stmt)
    rows = data if isinstance(data, list) else []
    return [TaskItem(**row) for row in rows]


async def get_backlinks(id: str) -> list[Backlink]:
    """[notes] Get all blocks that reference (link to) a given block or document.

    Essential for understanding how content is connected in the knowledge graph.
    Returns each backlink with its document title (doc_title) for context.

    Args:
        id: The block or document ID to find references to.
    """
    _sanitize(id)
    data = await sy.call("/api/ref/getBacklink", id=id)
    if not data:
        return []
    backlinks = data.get("backlinks", [])
    results: list[Backlink] = []
    for bl in backlinks:
        doc_title = bl.get("name", "")
        for block in bl.get("backlinks", []):
            results.append(Backlink(
                id=block.get("id", ""),
                content=block.get("content", ""),
                type=block.get("type", ""),
                hpath=block.get("hPath", ""),
                box=block.get("box", ""),
                doc_title=doc_title,
            ))
    return results


async def get_tags() -> list[TagCount]:
    """[notes] List all tags used across the workspace with their usage count.

    Useful for discovering how content is organized and finding tag-based entry points.
    """
    data = await sy.call("/api/tag/getTag")
    if not data:
        return []
    tags = data.get("tags", [])

    def _flatten(tag_list: list, prefix: str = "") -> list[TagCount]:
        results: list[TagCount] = []
        for t in tag_list:
            label = t.get("label", "")
            full = f"{prefix}/{label}" if prefix else label
            count = t.get("count", 0)
            results.append(TagCount(tag=full, count=count))
            children = t.get("tags", [])
            if children:
                results.extend(_flatten(children, full))
        return results

    return _flatten(tags)


# Span types SiYuan uses for an inline tag. Legacy content uses the bare
# 'tag'; spans written through the kernel API (our own create_document /
# update_block, and recent SiYuan builds) carry the compound textmark form,
# e.g. 'textmark tag' or 'textmark em tag' when the tag also has emphasis.
# CDI-1228: matching only the legacy 'tag' made search_by_tag blind to every
# tag this MCP creates. We enumerate the known variants explicitly rather than
# a blind LIKE '%tag%' so we never catch an unrelated future span type whose
# name merely contains "tag".
_TAG_SPAN_TYPES = ("tag", "textmark tag", "textmark em tag")


async def search_by_tag(tag: str) -> list[TaggedBlock]:
    """[notes] Find all blocks with a specific tag.

    Matches inline tags regardless of how they were authored — both the legacy
    ``type='tag'`` spans and the compound ``'textmark tag'`` / ``'textmark em
    tag'`` spans the kernel API writes (CDI-1228). The tag name is matched
    exactly on the span ``content`` (no substring leakage), so searching
    'decision' will not also return 'decisions'.

    Args:
        tag: The tag to search for (without #). e.g. 'porsche', 'wishlist'.
    """
    safe_tag = _sanitize(tag)
    type_list = ", ".join(f"'{t}'" for t in _TAG_SPAN_TYPES)
    stmt = (
        f"SELECT blocks.id, blocks.content, blocks.type, blocks.box, "
        f"blocks.hpath, blocks.updated "
        f"FROM spans INNER JOIN blocks ON spans.block_id = blocks.id "
        f"WHERE spans.type IN ({type_list}) AND spans.content = '{safe_tag}' "
        f"ORDER BY blocks.updated DESC LIMIT 50"
    )
    data = await sy.call("/api/query/sql", stmt=stmt)
    rows = data if isinstance(data, list) else []
    return [TaggedBlock(**row) for row in rows]


async def get_block_children(
    id: str,
    depth: Annotated[int, Field(ge=1, le=5)] = 2,
    ctx: Context | None = None,
) -> BlockChildren:
    """[notes] Get a block and its child blocks as a tree structure.

    Useful for understanding document outline or navigating into a section.
    Uses a single query per depth level instead of per-child queries.

    Args:
        id: The block or document ID to get children for.
        depth: How many levels deep to traverse (default 2, max 5).
    """
    safe_id = _sanitize(id)

    # Fetch all descendants up to the requested depth in one query per level
    # Start with the direct children
    all_blocks: dict[str, list[dict[str, Any]]] = {}  # parent_id -> children
    current_ids = [safe_id]

    for level in range(depth):
        if not current_ids:
            break
        if ctx is not None:
            try:
                await ctx.report_progress(
                    progress=level + 1,
                    total=depth,
                    message=f"depth level {level + 1}/{depth}",
                )
            except Exception:  # pragma: no cover - defensive
                logger.debug("ctx.report_progress failed", exc_info=True)
        id_list = ", ".join(f"'{_sanitize(cid)}'" for cid in current_ids)
        stmt = (
            f"SELECT id, content, type, sort, parent_id "
            f"FROM blocks WHERE parent_id IN ({id_list}) "
            f"ORDER BY sort ASC LIMIT 500"
        )
        data = await sy.call("/api/query/sql", stmt=stmt)
        rows = data if isinstance(data, list) else []

        next_ids = []
        for row in rows:
            pid = row.get("parent_id", "")
            all_blocks.setdefault(pid, []).append(row)
            next_ids.append(row.get("id", ""))
        current_ids = next_ids

    # Build tree from collected blocks
    def _build_tree(parent_id: str) -> list[dict[str, Any]]:
        children = all_blocks.get(parent_id, [])
        for child in children:
            child["children"] = _build_tree(child.get("id", ""))
        return children

    # Get the parent block info
    parent_data = await sy.call("/api/block/getBlockInfo", id=safe_id)
    return BlockChildren(
        id=id,
        content=parent_data.get("content", "") if parent_data else "",
        type=parent_data.get("type", "") if parent_data else "",
        children=_build_tree(safe_id),
    )


async def search_with_context(
    query: str,
    context_blocks: Annotated[int, Field(ge=0, le=10)] = 2,
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
) -> list[ContextSearchHit]:
    """[notes] Search SiYuan and return results with surrounding context blocks.

    Unlike basic search, this returns the blocks before and after each match,
    giving the LLM enough context to understand what was found.

    Args:
        query: Search query string.
        context_blocks: Number of sibling blocks to include before and after each match (default 2).
        limit: Max search results (default 10, max 50).
    """
    data = await sy.call(
        "/api/search/fullTextSearchBlock",
        query=query,
        method=0,
        types={"document": True, "heading": True, "paragraph": True, "list": True, "listItem": True},
        page=1,
        pageSize=limit,
    )
    blocks = data.get("blocks", []) if data else []

    results: list[ContextSearchHit] = []
    for b in blocks:
        block_id = b.get("id", "")
        context: list[dict[str, Any]] = []

        if context_blocks > 0 and block_id:
            safe_block_id = _sanitize(block_id)
            ctx_stmt = (
                f"SELECT id, content, type FROM blocks "
                f"WHERE parent_id = (SELECT parent_id FROM blocks WHERE id = '{safe_block_id}') "
                f"ORDER BY sort ASC"
            )
            siblings = await sy.call("/api/query/sql", stmt=ctx_stmt)
            if isinstance(siblings, list):
                idx = next((i for i, s in enumerate(siblings) if s.get("id") == block_id), -1)
                if idx >= 0:
                    start = max(0, idx - context_blocks)
                    end = min(len(siblings), idx + context_blocks + 1)
                    context = siblings[start:end]

        results.append(ContextSearchHit(
            id=block_id,
            content=b.get("content", ""),
            type=b.get("type", ""),
            hpath=b.get("hPath", ""),
            box=b.get("box", ""),
            root_id=b.get("rootID", ""),
            context=context,
        ))

    return results


async def capture_task(
    text: str,
    notebook: str = "",
) -> CaptureTaskResult:
    """[notes] Append a new task checkbox to today's daily note.

    This is a high-level convenience tool that combines listing notebooks,
    creating/opening the daily note, and appending a task — all in one call.

    Args:
        text: The task text (without checkbox markup — it will be added automatically).
        notebook: Optional notebook ID. If empty, uses the first open notebook.

    Returns:
        The daily note document ID and the appended block info.
    """
    # Resolve notebook if not provided
    if not notebook:
        nb_data = await sy.call("/api/notebook/lsNotebooks")
        notebooks = nb_data.get("notebooks", []) if nb_data else []
        open_nbs = [nb for nb in notebooks if not nb.get("closed", False)]
        if not open_nbs:
            return CaptureTaskResult(error="No open notebooks found")
        notebook = open_nbs[0]["id"]

    # Create or open today's daily note
    daily_id = await sy.call("/api/filetree/createDailyNote", notebook=notebook)
    if not daily_id:
        return CaptureTaskResult(error="Failed to create daily note")
    doc_id = daily_id if isinstance(daily_id, str) else str(daily_id)

    # Append the task
    task_md = f"* [ ] {text}"
    result = await sy.call(
        "/api/block/appendBlock",
        data=task_md,
        dataType="markdown",
        parentID=doc_id,
    )

    return CaptureTaskResult(
        ok=True,
        daily_note_id=doc_id,
        notebook=notebook,
        task=text,
        transactions=result if isinstance(result, list) else [],
    )


async def doc_exists(notebook: str, path: str) -> DocExistsResult:
    """[notes] Check if a document exists at ``notebook`` + ``hpath``.

    Lightweight existence check that does not error on miss. Saves a follow-up
    call by returning the matching ``block_id`` when found.

    Path matching uses SiYuan's canonical ``hpath`` format — the human-readable
    path without the ``.sy`` extension, e.g. ``/Projects/Foo`` (leading slash,
    no trailing slash). A path passed without a leading slash is treated as
    ``/<path>`` for convenience.

    Args:
        notebook: Notebook ID (the ``box`` column on the ``blocks`` table).
        path: Document hpath inside the notebook.

    Returns:
        ``{"exists": bool, "block_id": str | None, "hpath": str}``.
    """
    safe_nb = _sanitize(notebook)
    hpath = path if path.startswith("/") else f"/{path}"
    safe_hpath = _sanitize(hpath)
    stmt = (
        f"SELECT id FROM blocks "
        f"WHERE type = 'd' AND box = '{safe_nb}' AND hpath = '{safe_hpath}' "
        f"LIMIT 1"
    )
    data = await sy.call("/api/query/sql", stmt=stmt)
    rows = data if isinstance(data, list) else []
    if rows:
        return DocExistsResult(exists=True, block_id=rows[0].get("id"), hpath=hpath)
    return DocExistsResult(exists=False, block_id=None, hpath=hpath)


async def get_document_outline(
    id: str,
    limit: Annotated[int, Field(ge=1, le=200)] = 100,
) -> list[OutlineHeading]:
    """[notes] Get the heading outline of a document.

    Returns only heading blocks in order — useful for understanding document
    structure without fetching the full content or making N+1 queries.

    Args:
        id: The document block ID.
        limit: Max headings to return (default 100, max 200).
    """
    safe_id = _sanitize(id)
    stmt = (
        f"SELECT id, content, subtype AS level, sort "
        f"FROM blocks WHERE root_id = '{safe_id}' AND type = 'h' "
        f"ORDER BY sort ASC LIMIT {limit}"
    )
    data = await sy.call("/api/query/sql", stmt=stmt)
    rows = data if isinstance(data, list) else []
    return [OutlineHeading(**row) for row in rows]
