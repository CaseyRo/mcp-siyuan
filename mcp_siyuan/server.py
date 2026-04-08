"""FastMCP server for SiYuan Notes."""

from __future__ import annotations

import os

from fastmcp import FastMCP
from mcp.types import Icon

from mcp_siyuan.auth import BearerTokenVerifier
from mcp_siyuan.config import settings
from mcp_siyuan.tools.read import (
    get_block,
    get_block_attrs,
    get_document,
    list_notebooks,
    search,
    sql_query,
)
from mcp_siyuan.tools.smart import (
    capture_task,
    find_tasks,
    get_backlinks,
    get_block_children,
    get_document_outline,
    get_recent_docs,
    get_tags,
    search_by_tag,
    search_with_context,
)
from mcp_siyuan.tools.export import export_pdf
from mcp_siyuan.tools.write import (
    append_block,
    create_document,
    create_notebook,
    daily_note,
    delete_block,
    insert_block,
    move_block,
    move_doc,
    remove_notebook,
    rename_doc,
    rename_notebook,
    set_block_attrs,
    update_block,
)

_api_key = os.getenv("MCP_API_KEY", "")
_auth = BearerTokenVerifier(api_key=_api_key) if _api_key else None


mcp = FastMCP(
    "mcp-siyuan",
    auth=_auth,
    icons=[
        Icon(
            src="https://b3log.org/images/brand/siyuan-128.png",
            mimeType="image/png",
            sizes=["128x128"],
        ),
    ],
)

# Tier 1 — Read / Query
mcp.tool(list_notebooks)
mcp.tool(sql_query)
mcp.tool(get_document)
mcp.tool(search)
mcp.tool(get_block)
mcp.tool(get_block_attrs)

# Tier 2 — Write
mcp.tool(create_notebook)
mcp.tool(rename_notebook)
mcp.tool(remove_notebook)
mcp.tool(create_document)
mcp.tool(update_block)
mcp.tool(insert_block)
mcp.tool(append_block)
mcp.tool(delete_block)
mcp.tool(set_block_attrs)
mcp.tool(move_doc)
mcp.tool(rename_doc)
mcp.tool(move_block)
mcp.tool(daily_note)

# Smart — LLM-ergonomic high-level tools
mcp.tool(get_recent_docs)
mcp.tool(find_tasks)
mcp.tool(get_backlinks)
mcp.tool(get_tags)
mcp.tool(search_by_tag)
mcp.tool(get_block_children)
mcp.tool(search_with_context)
mcp.tool(capture_task)
mcp.tool(get_document_outline)

# Export
mcp.tool(export_pdf)


def main() -> None:
    """Entry point for the mcp-siyuan server."""
    if settings.transport == "http":
        mcp.run(transport="http", host=settings.host, port=settings.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
