"""FastMCP server for SiYuan Notes."""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_siyuan.config import settings
from mcp_siyuan.tools.read import (
    siyuan_get_block,
    siyuan_get_block_attrs,
    siyuan_get_document,
    siyuan_list_notebooks,
    siyuan_search,
    siyuan_sql_query,
)
from mcp_siyuan.tools.smart import (
    siyuan_find_tasks,
    siyuan_get_backlinks,
    siyuan_get_block_children,
    siyuan_get_recent_docs,
    siyuan_get_tags,
    siyuan_search_by_tag,
    siyuan_search_with_context,
)
from mcp_siyuan.tools.write import (
    siyuan_append_block,
    siyuan_create_document,
    siyuan_daily_note,
    siyuan_insert_block,
    siyuan_set_block_attrs,
    siyuan_update_block,
)

mcp = FastMCP("mcp-siyuan")

# Tier 1 — Read / Query
mcp.tool(siyuan_list_notebooks)
mcp.tool(siyuan_sql_query)
mcp.tool(siyuan_get_document)
mcp.tool(siyuan_search)
mcp.tool(siyuan_get_block)
mcp.tool(siyuan_get_block_attrs)

# Tier 2 — Write
mcp.tool(siyuan_create_document)
mcp.tool(siyuan_update_block)
mcp.tool(siyuan_insert_block)
mcp.tool(siyuan_append_block)
mcp.tool(siyuan_set_block_attrs)
mcp.tool(siyuan_daily_note)

# Smart — LLM-ergonomic high-level tools
mcp.tool(siyuan_get_recent_docs)
mcp.tool(siyuan_find_tasks)
mcp.tool(siyuan_get_backlinks)
mcp.tool(siyuan_get_tags)
mcp.tool(siyuan_search_by_tag)
mcp.tool(siyuan_get_block_children)
mcp.tool(siyuan_search_with_context)


def main() -> None:
    """Entry point for the mcp-siyuan server."""
    if settings.transport == "http":
        mcp.run(transport="http", host=settings.host, port=settings.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
