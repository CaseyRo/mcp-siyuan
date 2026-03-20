"""High-level, LLM-ergonomic tools for SiYuan."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from mcp_siyuan.client import sy


async def siyuan_get_recent_docs(
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
    notebook: str = "",
) -> list[dict[str, Any]]:
    """Get recently modified documents, newest first.

    Great for understanding what the user has been working on lately.

    Args:
        limit: Max number of documents to return (default 10, max 50).
        notebook: Optional notebook ID to filter by. Empty = all notebooks.
    """
    where = "WHERE type = 'd'"
    if notebook:
        where += f" AND box = '{notebook}'"
    stmt = f"SELECT id, content AS title, box, hpath, updated FROM blocks {where} ORDER BY updated DESC LIMIT {limit}"
    data = await sy.call("/api/query/sql", stmt=stmt)
    return data if isinstance(data, list) else []


async def siyuan_find_tasks(
    notebook: str = "",
    checked: bool = False,
    days: Annotated[int, Field(ge=1, le=365)] = 7,
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
) -> list[dict[str, Any]]:
    """Find task/TODO items across SiYuan notes.

    Searches for task list items (checkbox blocks). Perfect for extracting
    TODOs from daily notes for export to task managers.

    Args:
        notebook: Optional notebook ID to scope the search. Empty = all notebooks.
        checked: If True, return completed tasks. If False (default), return open/unchecked tasks.
        days: Look back this many days (default 7).
        limit: Max results (default 50, max 100).
    """
    subtype_filter = "'t'" if not checked else "'d'"
    where = f"WHERE type = 'i' AND subtype = {subtype_filter}"
    if notebook:
        where += f" AND box = '{notebook}'"
    where += f" AND updated >= strftime('%Y%m%d%H%M%S', datetime('now', '-{days} days'))"

    stmt = f"SELECT id, content, box, hpath, root_id, updated FROM blocks {where} ORDER BY updated DESC LIMIT {limit}"
    data = await sy.call("/api/query/sql", stmt=stmt)
    return data if isinstance(data, list) else []


async def siyuan_get_backlinks(id: str) -> list[dict[str, Any]]:
    """Get all blocks that reference (link to) a given block or document.

    Essential for understanding how content is connected in the knowledge graph.

    Args:
        id: The block or document ID to find references to.
    """
    data = await sy.call("/api/ref/getBacklink", id=id)
    if not data:
        return []
    backlinks = data.get("backlinks", [])
    results = []
    for bl in backlinks:
        for block in bl.get("backlinks", []):
            results.append({
                "id": block.get("id", ""),
                "content": block.get("content", ""),
                "type": block.get("type", ""),
                "hpath": block.get("hPath", ""),
                "box": block.get("box", ""),
            })
    return results


async def siyuan_get_tags() -> list[dict[str, Any]]:
    """List all tags used across the workspace with their usage count.

    Useful for discovering how content is organized and finding tag-based entry points.
    """
    data = await sy.call("/api/tag/getTag")
    if not data:
        return []
    tags = data.get("tags", [])

    def _flatten(tag_list: list, prefix: str = "") -> list[dict[str, Any]]:
        results = []
        for t in tag_list:
            label = t.get("label", "")
            full = f"{prefix}/{label}" if prefix else label
            count = t.get("count", 0)
            results.append({"tag": full, "count": count})
            children = t.get("tags", [])
            if children:
                results.extend(_flatten(children, full))
        return results

    return _flatten(tags)


async def siyuan_search_by_tag(tag: str) -> list[dict[str, Any]]:
    """Find all blocks with a specific tag.

    Args:
        tag: The tag to search for (without #). e.g. 'porsche', 'wishlist'.
    """
    stmt = f"SELECT blocks.id, blocks.content, blocks.type, blocks.box, blocks.hpath, blocks.updated FROM spans INNER JOIN blocks ON spans.block_id = blocks.id WHERE spans.type = 'tag' AND spans.content LIKE '%{tag}%' ORDER BY blocks.updated DESC LIMIT 50"
    data = await sy.call("/api/query/sql", stmt=stmt)
    return data if isinstance(data, list) else []


async def siyuan_get_block_children(
    id: str,
    depth: Annotated[int, Field(ge=1, le=5)] = 2,
) -> dict[str, Any]:
    """Get a block and its child blocks as a tree structure.

    Useful for understanding document outline or navigating into a section.

    Args:
        id: The block or document ID to get children for.
        depth: How many levels deep to traverse (default 2, max 5).
    """
    stmt = f"SELECT id, content, type, sort, parent_id FROM blocks WHERE parent_id = '{id}' ORDER BY sort ASC LIMIT 100"
    data = await sy.call("/api/query/sql", stmt=stmt)
    children = data if isinstance(data, list) else []

    if depth > 1:
        for child in children:
            child_id = child.get("id", "")
            if child_id:
                sub = await siyuan_get_block_children(child_id, depth=depth - 1)
                child["children"] = sub.get("children", [])
    else:
        for child in children:
            child["children"] = []

    # Get the parent block info
    parent_data = await sy.call("/api/block/getBlockInfo", id=id)
    return {
        "id": id,
        "content": parent_data.get("content", "") if parent_data else "",
        "type": parent_data.get("type", "") if parent_data else "",
        "children": children,
    }


async def siyuan_search_with_context(
    query: str,
    context_blocks: Annotated[int, Field(ge=0, le=10)] = 2,
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
) -> list[dict[str, Any]]:
    """Search SiYuan and return results with surrounding context blocks.

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

    results = []
    for b in blocks:
        block_id = b.get("id", "")
        entry: dict[str, Any] = {
            "id": block_id,
            "content": b.get("content", ""),
            "type": b.get("type", ""),
            "hpath": b.get("hPath", ""),
            "box": b.get("box", ""),
            "root_id": b.get("rootID", ""),
        }

        if context_blocks > 0 and block_id:
            ctx_stmt = (
                f"SELECT id, content, type FROM blocks "
                f"WHERE parent_id = (SELECT parent_id FROM blocks WHERE id = '{block_id}') "
                f"ORDER BY sort ASC"
            )
            siblings = await sy.call("/api/query/sql", stmt=ctx_stmt)
            if isinstance(siblings, list):
                idx = next((i for i, s in enumerate(siblings) if s.get("id") == block_id), -1)
                if idx >= 0:
                    start = max(0, idx - context_blocks)
                    end = min(len(siblings), idx + context_blocks + 1)
                    entry["context"] = siblings[start:end]

        results.append(entry)

    return results
