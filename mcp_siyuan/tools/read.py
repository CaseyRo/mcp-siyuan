"""Tier 1 — Read / Query tools for SiYuan."""

from __future__ import annotations

import re
from typing import Annotated, Any

from pydantic import Field

from mcp_siyuan.client import sy
from mcp_siyuan.models import BlockInfo, NotebookInfo, SearchHit, SqlRow

_ALLOWED_STMT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_MAX_SQL_ROWS = 200


async def list_notebooks() -> list[NotebookInfo]:
    """[notes] List all notebooks in the SiYuan workspace.

    Use this first to discover notebook IDs before creating documents or daily notes.
    Notebooks with closed=true cannot accept new documents.
    """
    from mcp_siyuan.models import Notebook

    data = await sy.call("/api/notebook/lsNotebooks")
    raw = data.get("notebooks", []) if data else []
    return [NotebookInfo(**Notebook(**nb).model_dump()) for nb in raw]


async def sql_query(stmt: str) -> list[SqlRow]:
    """[notes] Execute a read-only SQL SELECT against SiYuan's internal database.

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
    rows = data if isinstance(data, list) else []
    return [SqlRow(**row) for row in rows]


async def get_document(
    id: str,
    max_length: Annotated[int, Field(ge=1, le=524288)] = 65536,
) -> str:
    """[notes] Get a document's markdown content by its block ID.

    Args:
        id: The document block ID.
        max_length: Maximum characters to return (default 65536, max 524288). Content exceeding this is truncated.
    """
    data = await sy.call("/api/export/exportMdContent", id=id)
    content = data.get("content", "") if data else ""
    if len(content) > max_length:
        content = content[:max_length] + f"\n\n[... truncated at {max_length} chars]"
    return content


async def search(
    query: str,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
) -> list[SearchHit]:
    """[notes] Quick full-text search across all SiYuan content (no surrounding context).

    Disambiguation: For notes/documents → siyuan. For social media posts → zernio. For blog/writing content → writings.

    For richer results with surrounding blocks, use search_with_context instead.

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
        SearchHit(
            id=b.get("id", ""),
            content=b.get("content", ""),
            root_id=b.get("rootID", ""),
            box=b.get("box", ""),
            hpath=b.get("hPath", ""),
        )
        for b in blocks
    ]


_BLOCK_FIELDS = ("id", "type", "content", "parent_id", "root_id", "box", "hpath", "updated")
# Kramdown inline attribute lists, e.g. {: id="2026..." updated="2026..."}
_IAL_RE = re.compile(r'\{: (?:[\w-]+="[^"]*"\s*)+\}')


async def get_block(id: str) -> BlockInfo:
    """[notes] Get a single block's content and metadata by ID.

    Returns id, type, content (plain text), markdown, parent_id, root_id, box,
    hpath and updated. Content comes from the kernel, so it is current even
    when the SQL index lags. For custom attributes (memo, alias, bookmark,
    etc.), use get_block_attrs instead.

    Args:
        id: The block ID to retrieve.
    """
    from mcp_siyuan.client import SiYuanError

    if any(c in id for c in ("'", '"', ";", "\n")):
        return BlockInfo(error=f"Block {id} not found")
    rows = await sy.call(
        "/api/query/sql",
        stmt=f"SELECT {', '.join(_BLOCK_FIELDS)}, markdown FROM blocks "
        f"WHERE id = '{id}' LIMIT 1",
    )
    row = rows[0] if isinstance(rows, list) and rows else {}
    try:
        kd = await sy.call("/api/block/getBlockKramdown", id=id)
    except SiYuanError:
        kd = None
    markdown = _IAL_RE.sub("", (kd or {}).get("kramdown") or "").strip()
    if not row and not markdown:
        return BlockInfo(error=f"Block {id} not found")

    fields: dict[str, Any] = {k: row.get(k) or "" for k in _BLOCK_FIELDS}
    if not row:
        # Not indexed yet: take what the kernel knows. parent/type stay empty.
        try:
            info = await sy.call("/api/block/getBlockInfo", id=id) or {}
        except SiYuanError:
            info = {}
        fields.update(id=id, root_id=info.get("rootID", ""), box=info.get("box", ""))
    fields["markdown"] = markdown or row.get("markdown") or ""
    fields["content"] = fields["content"] or fields["markdown"]
    return BlockInfo(**fields)


async def get_block_attrs(id: str) -> dict[str, str]:
    """[notes] Get all attributes (system and custom) for a block.

    Returns system and custom attributes. For block content and markdown,
    use get_block instead.

    Args:
        id: The block ID to retrieve attributes for.
    """
    data = await sy.call("/api/attr/getBlockAttrs", id=id)
    return data if isinstance(data, dict) else {}
