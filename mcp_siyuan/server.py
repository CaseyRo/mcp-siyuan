"""FastMCP server for SiYuan Notes."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata

import fastmcp
from fastmcp import FastMCP
from mcp.types import Icon
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_siyuan import __version__
from mcp_siyuan.auth import BearerTokenVerifier
from mcp_siyuan.client import sy
from mcp_siyuan.config import settings
from mcp_siyuan.observability import diag_buffer
from mcp_siyuan.observability.logging_setup import configure_logging
from mcp_siyuan.observability.tracing import traced_tool
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

configure_logging()
logger = logging.getLogger(__name__)


def _check_fastmcp_version() -> None:
    """Log FastMCP version at startup; warn loudly on pin mismatch."""
    expected = "3.2.4"
    try:
        installed = importlib_metadata.version("fastmcp")
    except importlib_metadata.PackageNotFoundError:
        installed = getattr(fastmcp, "__version__", "unknown")
    logger.info("fastmcp loaded", extra={"fastmcp_version": installed})
    if installed != expected:
        logger.error(
            "fastmcp version mismatch: expected %s, got %s. Pinning is intentional "
            "for the No-approval-received RCA.",
            expected,
            installed,
        )


_check_fastmcp_version()

_api_key = settings.mcp_api_key
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
mcp.tool(traced_tool(list_notebooks))
mcp.tool(traced_tool(sql_query))
mcp.tool(traced_tool(get_document))
mcp.tool(traced_tool(search))
mcp.tool(traced_tool(get_block))
mcp.tool(traced_tool(get_block_attrs))

# Tier 2 — Write
mcp.tool(traced_tool(create_notebook))
mcp.tool(traced_tool(rename_notebook))
mcp.tool(traced_tool(remove_notebook))
mcp.tool(traced_tool(create_document))
mcp.tool(traced_tool(update_block))
mcp.tool(traced_tool(insert_block))
mcp.tool(traced_tool(append_block))
mcp.tool(traced_tool(delete_block))
mcp.tool(traced_tool(set_block_attrs))
mcp.tool(traced_tool(move_doc))
mcp.tool(traced_tool(rename_doc))
mcp.tool(traced_tool(move_block))
mcp.tool(traced_tool(daily_note))

# Smart — LLM-ergonomic high-level tools
mcp.tool(traced_tool(get_recent_docs))
mcp.tool(traced_tool(find_tasks))
mcp.tool(traced_tool(get_backlinks))
mcp.tool(traced_tool(get_tags))
mcp.tool(traced_tool(search_by_tag))
mcp.tool(traced_tool(get_block_children))
mcp.tool(traced_tool(search_with_context))
mcp.tool(traced_tool(capture_task))
mcp.tool(traced_tool(get_document_outline))

# Export
mcp.tool(traced_tool(export_pdf))


# --- Health endpoint + upstream probe -------------------------------------
_start_time = datetime.now(timezone.utc)
_probe_ttl = settings.upstream_probe_interval
_probe_state: dict = {"ok": False, "checked_at": 0.0}


async def _probe_upstream() -> bool:
    """Probe SiYuan kernel. Cached up to _probe_ttl seconds."""
    now = time.monotonic()
    if now - _probe_state["checked_at"] < _probe_ttl:
        return _probe_state["ok"]
    try:
        # Cap probe at 2s so /health always responds before the Docker
        # healthcheck's 3s urllib timeout (httpx default is 30s).
        await asyncio.wait_for(
            sy.call("/api/system/bootProgress"), timeout=2.0
        )
        if not _probe_state["ok"]:
            logger.info("Upstream SiYuan kernel reachable")
        _probe_state["ok"] = True
    except asyncio.TimeoutError:
        if _probe_state["ok"] or _probe_state["checked_at"] == 0.0:
            logger.error("Upstream SiYuan kernel probe timed out (>2s)")
        _probe_state["ok"] = False
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

    Pass ?diag=1 to also include a snapshot of the recent-tool-call ring buffer
    (size SIYUAN_DIAG_BUFFER_SIZE, default 50).
    """
    upstream_ok = await _probe_upstream()
    payload: dict = {
        "status": "healthy" if upstream_ok else "degraded",
        "service": "mcp-siyuan",
        "version": __version__,
        "upstream_reachable": upstream_ok,
        "uptime_seconds": int(
            (datetime.now(timezone.utc) - _start_time).total_seconds()
        ),
    }
    if request.query_params.get("diag") == "1":
        payload["diag"] = diag_buffer.snapshot()
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
