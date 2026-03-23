"""Tier 1 — Read / Query tools for SiYuan."""

from __future__ import annotations

import re
from typing import Annotated, Any

from pydantic import Field

from mcp_siyuan.client import sy

_ALLOWED_STMT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_MAX_SQL_ROWS = 200


async def siyuan_list_notebooks() -> list[dict[str, Any]]:
    """List all notebooks in the SiYuan workspace.

    Use this first to discover notebook IDs before creating documents or daily notes.
    Notebooks with closed=true cannot accept new documents.
    """
    from mcp_siyuan.models import Notebook

    data = await sy.call("/api/notebook/lsNotebooks")
    raw = data.get("notebooks", []) if data else []
    return [Notebook(**nb).model_dump() for nb in raw]


async def siyuan_sql_query(stmt: str) -> list[dict[str, Any]]:
    """Execute a read-only SQL SELECT against SiYuan's internal database.

    Only SELECT statements are permitted. A LIMIT is enforced if not provided.

    Tables and key columns:
      blocks: id, parent_id, root_id, box, path, hpath, name, content,
              markdown, type, subtype, sort, created, updated
      spans:  id, block_id, content, type (e.g. 'tag', 'a')
      refs:   id, block_id, def_block_id, content, type
      attributes: id, block_id, name, value

    Block types: d=document, h=heading, p=paragraph, l=list, i=listItem,
                 c=code, m=math, t=table, s=superBlock, b=blockquote

    Example: SELECT id, content FROM blocks WHERE content LIKE '%TODO%' LIMIT 10
    """
    if not _ALLOWED_STMT_RE.match(stmt):
        raise ValueError("Only SELECT statements are permitted.")
    if not re.search(r"\bLIMIT\s+\d+", stmt, re.IGNORECASE):
        stmt = stmt.rstrip("; \t\n") + f" LIMIT {_MAX_SQL_ROWS}"
    data = await sy.call("/api/query/sql", stmt=stmt)
    return data if isinstance(data, list) else []


async def siyuan_get_document(
    id: str,
    max_length: Annotated[int, Field(ge=1, le=524288)] = 65536,
) -> str:
    """Get a document's markdown content by its block ID.

    Args:
        id: The document block ID.
        max_length: Maximum characters to return (default 65536, max 524288). Content exceeding this is truncated.
    """
    data = await sy.call("/api/export/exportMdContent", id=id)
    content = data.get("content", "") if data else ""
    if len(content) > max_length:
        content = content[:max_length] + f"\n\n[... truncated at {max_length} chars]"
    return content


async def siyuan_search(
    query: str,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
) -> list[dict[str, Any]]:
    """Quick full-text search across all SiYuan content (no surrounding context).

    For richer results with surrounding blocks, use siyuan_search_with_context instead.

    Args:
        query: Search query string.
        limit: Maximum number of results (default 20, max 100).
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
    return [
        {
            "id": b.get("id", ""),
            "content": b.get("content", ""),
            "root_id": b.get("rootID", ""),
            "box": b.get("box", ""),
            "hpath": b.get("hPath", ""),
        }
        for b in blocks
    ]


_BLOCK_FIELDS = ("id", "type", "content", "parent_id", "root_id", "box", "hpath", "updated")


async def siyuan_get_block(id: str) -> dict[str, Any]:
    """Get a single block's content and metadata by ID.

    Returns only the essential fields: id, type, content, parent_id,
    root_id, box, hpath, updated.

    Args:
        id: The block ID to retrieve.
    """
    data = await sy.call("/api/block/getBlockInfo", id=id)
    if not data:
        return {"error": f"Block {id} not found"}
    # Normalise field names and project only useful fields
    normalised: dict[str, Any] = {}
    for key in _BLOCK_FIELDS:
        # SiYuan uses camelCase for some fields in this endpoint
        camel = {"parent_id": "parentID", "root_id": "rootID", "hpath": "hPath"}.get(key, key)
        normalised[key] = data.get(key) or data.get(camel, "")
    return normalised


async def siyuan_get_block_attrs(id: str) -> dict[str, str]:
    """Get all attributes (system and custom) for a block.

    Args:
        id: The block ID to retrieve attributes for.
    """
    data = await sy.call("/api/attr/getBlockAttrs", id=id)
    return data if isinstance(data, dict) else {}
