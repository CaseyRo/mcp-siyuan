"""FastMCP server for SiYuan Notes."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from fastmcp import FastMCP
from mcp.types import Icon
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_siyuan import __version__
from mcp_siyuan.auth import BearerTokenVerifier
from mcp_siyuan.client import sy
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

logger = logging.getLogger(__name__)

_api_key = os.getenv("MCP_API_KEY", "")
if settings.transport == "http" and not _api_key:
    raise SystemExit(
        "MCP_API_KEY is required in HTTP mode. Refusing to start "
        "an unauthenticated server."
    )
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


# --- Health endpoint + upstream probe -------------------------------------
_start_time = datetime.now(timezone.utc)
_probe_ttl = int(os.getenv("UPSTREAM_PROBE_INTERVAL", "30"))
_probe_state: dict = {"ok": False, "checked_at": 0.0}


async def _probe_upstream() -> bool:
    """Probe SiYuan kernel. Cached up to _probe_ttl seconds."""
    now = time.monotonic()
    if now - _probe_state["checked_at"] < _probe_ttl:
        return _probe_state["ok"]
    try:
        await sy.call("/api/system/bootProgress")
        if not _probe_state["ok"]:
            logger.info("Upstream SiYuan kernel reachable")
        _probe_state["ok"] = True
    except Exception as exc:
        if _probe_state["ok"] or _probe_state["checked_at"] == 0.0:
            logger.error("Upstream SiYuan kernel probe failed: %s", exc)
        _probe_state["ok"] = False
    _probe_state["checked_at"] = now
    return _probe_state["ok"]


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Public health endpoint: reports MCP + upstream reachability.

    Returns HTTP 200 when upstream is reachable, 503 when not.
    Probe result is cached for UPSTREAM_PROBE_INTERVAL seconds (default 30s)
    so healthcheck polling does not amplify upstream load.
    """
    upstream_ok = await _probe_upstream()
    payload = {
        "status": "healthy" if upstream_ok else "degraded",
        "service": "mcp-siyuan",
        "version": __version__,
        "upstream_reachable": upstream_ok,
        "uptime_seconds": int(
            (datetime.now(timezone.utc) - _start_time).total_seconds()
        ),
    }
    return JSONResponse(
        payload, status_code=200 if upstream_ok else 503
    )


@mcp.custom_route("/healthz", methods=["GET"])
async def health_check_z(request: Request) -> JSONResponse:
    """Alias for /health (k8s-style path)."""
    return await health_check(request)


def main() -> None:
    """Entry point for the mcp-siyuan server."""
    if settings.transport == "http":
        # stateless_http=True so Cloudflare-killed idle connections do not
        # leave orphaned MCP sessions. See openspec mcp-stateless-transport.
        mcp.run(
            transport="streamable-http",
            host=settings.host,
            port=settings.port,
            stateless_http=True,
        )
    else:
        mcp.run()


if __name__ == "__main__":
    main()
