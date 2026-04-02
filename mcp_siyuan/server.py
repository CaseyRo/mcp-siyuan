"""FastMCP server for SiYuan Notes."""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_siyuan.auth import create_auth
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
    siyuan_capture_task,
    siyuan_find_tasks,
    siyuan_get_backlinks,
    siyuan_get_block_children,
    siyuan_get_document_outline,
    siyuan_get_recent_docs,
    siyuan_get_tags,
    siyuan_search_by_tag,
    siyuan_search_with_context,
)
from mcp_siyuan.tools.write import (
    siyuan_append_block,
    siyuan_create_document,
    siyuan_create_notebook,
    siyuan_daily_note,
    siyuan_delete_block,
    siyuan_insert_block,
    siyuan_move_block,
    siyuan_move_doc,
    siyuan_remove_notebook,
    siyuan_rename_doc,
    siyuan_rename_notebook,
    siyuan_set_block_attrs,
    siyuan_update_block,
)

def _build_auth():
    """Build auth provider if running in HTTP mode."""
    if settings.transport != "http":
        return None
    if not settings.keycloak_client_secret:
        import logging

        logging.getLogger(__name__).warning(
            "KEYCLOAK_CLIENT_SECRET is empty — OAuth/OIDC auth disabled"
        )
        return None
    api_key = settings.ensure_api_key()
    return create_auth(
        api_key=api_key,
        base_url=settings.base_url,
        keycloak_issuer=settings.keycloak_issuer,
        keycloak_audience=settings.keycloak_audience,
        keycloak_client_id=settings.keycloak_client_id,
        keycloak_client_secret=settings.keycloak_client_secret,
    )


mcp = FastMCP("mcp-siyuan", auth=_build_auth())

# Tier 1 — Read / Query
mcp.tool(siyuan_list_notebooks)
mcp.tool(siyuan_sql_query)
mcp.tool(siyuan_get_document)
mcp.tool(siyuan_search)
mcp.tool(siyuan_get_block)
mcp.tool(siyuan_get_block_attrs)

# Tier 2 — Write
mcp.tool(siyuan_create_notebook)
mcp.tool(siyuan_rename_notebook)
mcp.tool(siyuan_remove_notebook)
mcp.tool(siyuan_create_document)
mcp.tool(siyuan_update_block)
mcp.tool(siyuan_insert_block)
mcp.tool(siyuan_append_block)
mcp.tool(siyuan_delete_block)
mcp.tool(siyuan_set_block_attrs)
mcp.tool(siyuan_move_doc)
mcp.tool(siyuan_rename_doc)
mcp.tool(siyuan_move_block)
mcp.tool(siyuan_daily_note)

# Smart — LLM-ergonomic high-level tools
mcp.tool(siyuan_get_recent_docs)
mcp.tool(siyuan_find_tasks)
mcp.tool(siyuan_get_backlinks)
mcp.tool(siyuan_get_tags)
mcp.tool(siyuan_search_by_tag)
mcp.tool(siyuan_get_block_children)
mcp.tool(siyuan_search_with_context)
mcp.tool(siyuan_capture_task)
mcp.tool(siyuan_get_document_outline)


def main() -> None:
    """Entry point for the mcp-siyuan server."""
    if settings.transport == "http":
        mcp.run(transport="http", host=settings.host, port=settings.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
