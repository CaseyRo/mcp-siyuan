"""FastMCP server for SiYuan Notes."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata

import fastmcp
from fastmcp import FastMCP
from mcp.types import Icon, ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_siyuan import __version__
from mcp_siyuan.auth import BearerTokenVerifier
from mcp_siyuan.client import sy
from mcp_siyuan.config import settings
from mcp_siyuan.models import OutlineHeading
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
    doc_exists,
    find_tasks,
    get_backlinks,
    get_block_children,
    get_doc_summary,
    get_document_outline,
    get_recent_docs,
    get_tags,
    list_conflicts,
    list_documents,
    list_orphans,
    search_by_tag,
    search_with_context,
)
from mcp_siyuan.tools.export import export_pdf
from mcp_siyuan.tools.write import (
    append_block,
    append_to_section,
    bulk_create_documents,
    bulk_set_attrs,
    create_document,
    create_notebook,
    daily_note,
    delete_block,
    delete_doc,
    get_or_create_doc,
    insert_block,
    move_block,
    move_doc,
    remove_notebook,
    rename_doc,
    rename_notebook,
    set_block_attrs,
    update_block,
    upsert_section,
)

configure_logging()
logger = logging.getLogger(__name__)


def _check_fastmcp_version() -> None:
    """Log FastMCP version at startup; warn loudly if outside the pinned range."""
    expected = "3.4.2"  # floor pin (see pyproject: >=3.4.2,<4.0.0)
    try:
        installed = importlib_metadata.version("fastmcp")
    except importlib_metadata.PackageNotFoundError:
        installed = getattr(fastmcp, "__version__", "unknown")
    logger.info("fastmcp loaded", extra={"fastmcp_version": installed})
    if installed.split(".")[0] != expected.split(".")[0]:
        logger.error(
            "fastmcp version mismatch: expected %s.x (>=%s,<4.0.0), got %s. "
            "Annotation/structured-output ergonomics may differ.",
            expected.split(".")[0],
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


_INSTRUCTIONS = """\
mcp-siyuan is a sidecar over a single SiYuan Notes workspace (a block-based
markdown knowledge base). Documents, headings, paragraphs, lists and list-items
are all *blocks* addressed by a 14-digit-timestamp ID (e.g. 20210808180320-fqgskfj).
Notebooks group documents; a document's location is its `hpath` (e.g. /Projects/Foo).

How to pick a tool:
- Discover first: `siyuan_list_notebooks` for notebook IDs, then SQL or search.
- Query is SQL-first: `siyuan_sql_query` runs read-only SELECTs against the
  blocks/spans/refs/attributes tables — see the `siyuan://schema` resource for the
  column legend and block-type codes. Prefer the smart wrappers when they fit:
  `siyuan_search` / `siyuan_search_with_context` (full-text), `siyuan_find_tasks`
  (open/closed checkboxes with parent doc title), `siyuan_get_recent_docs`,
  `siyuan_get_backlinks`, `siyuan_get_tags` / `siyuan_search_by_tag`,
  `siyuan_get_document_outline`, `siyuan_get_block_children`.
- Read content with `siyuan_get_document` (markdown) or `siyuan_get_block` /
  `siyuan_get_block_attrs` (single block).
- Write idempotently: prefer `siyuan_get_or_create_doc`, `siyuan_upsert_section`
  and `siyuan_append_to_section` over raw block inserts. `siyuan_capture_task`
  resolves a notebook + daily note + checkbox in one call. Every write tool takes
  an optional `idempotency_key` so retries don't duplicate.
- Destructive ops (`siyuan_remove_notebook`, `siyuan_delete_doc`,
  `siyuan_delete_block`, `siyuan_move_doc`) are annotated destructive — confirm intent.

Disambiguation across the fleet: notes/documents -> this server (siyuan);
social posts -> zernio; blog/long-form writing -> writings.

Single-replica: in-process idempotency + diag caches assume one instance.
"""

mcp = FastMCP(
    "mcp-siyuan",
    instructions=_INSTRUCTIONS,
    auth=_auth,
    icons=[
        Icon(
            src="https://b3log.org/images/brand/siyuan-128.png",
            mimeType="image/png",
            sizes=["128x128"],
        ),
    ],
)


def _register(
    func,
    *,
    title: str,
    tags: set[str],
    read_only: bool = False,
    destructive: bool = False,
    idempotent: bool = False,
    open_world: bool = True,
) -> None:
    """Register a traced tool with annotations + tags.

    Every SiYuan tool touches the external kernel, so ``openWorldHint`` defaults
    to True. The traced_tool wrapper preserves the wrapped signature, so FastMCP
    still introspects the real parameters and (where present) the ``ctx`` arg.
    """
    annotations = ToolAnnotations(
        title=title,
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )
    mcp.tool(traced_tool(func), annotations=annotations, tags=tags)


# Tier 1 — Read / Query (pure reads)
_register(list_notebooks, title="List notebooks", tags={"read"}, read_only=True, idempotent=True)
_register(sql_query, title="SQL query (read-only)", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(get_document, title="Get document markdown", tags={"read"}, read_only=True, idempotent=True)
_register(search, title="Full-text search", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(get_block, title="Get block", tags={"read"}, read_only=True, idempotent=True)
_register(get_block_attrs, title="Get block attributes", tags={"read"}, read_only=True, idempotent=True)

# Tier 2 — Write
_register(create_notebook, title="Create notebook", tags={"write"})
_register(rename_notebook, title="Rename notebook", tags={"write"}, idempotent=True)
_register(remove_notebook, title="Remove notebook", tags={"write", "destructive"}, destructive=True)
_register(create_document, title="Create document", tags={"write"})
_register(get_or_create_doc, title="Get or create document", tags={"write", "smart"}, idempotent=True)
_register(update_block, title="Update block", tags={"write"}, idempotent=True)
_register(insert_block, title="Insert block", tags={"write"})
_register(append_block, title="Append block", tags={"write"})
_register(upsert_section, title="Upsert section", tags={"write", "smart"}, idempotent=True)
_register(append_to_section, title="Append to section", tags={"write", "smart"})
_register(delete_block, title="Delete block", tags={"write", "destructive"}, destructive=True, idempotent=True)
_register(delete_doc, title="Delete document", tags={"write", "destructive"}, destructive=True, idempotent=True)
_register(set_block_attrs, title="Set block attributes", tags={"write"}, idempotent=True)
_register(move_doc, title="Move document(s)", tags={"write", "destructive"}, destructive=True)
_register(rename_doc, title="Rename document", tags={"write"}, idempotent=True)
_register(move_block, title="Move block", tags={"write"})
_register(daily_note, title="Open today's daily note", tags={"write", "smart"}, idempotent=True)
_register(bulk_create_documents, title="Bulk create documents", tags={"write"})
_register(bulk_set_attrs, title="Bulk set block attributes", tags={"write"}, idempotent=True)

# Smart — LLM-ergonomic high-level tools (reads)
_register(get_recent_docs, title="Recently modified documents", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(list_documents, title="List documents by title", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(find_tasks, title="Find tasks / TODOs", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(get_backlinks, title="Get backlinks", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(get_tags, title="List tags", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(search_by_tag, title="Search by tag", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(get_block_children, title="Get block children tree", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(search_with_context, title="Search with context", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(capture_task, title="Capture task to daily note", tags={"write", "smart"})
_register(get_document_outline, title="Get document outline", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(doc_exists, title="Document exists?", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(get_doc_summary, title="Get document summary", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(list_conflicts, title="List sync-conflict / malformed docs", tags={"read", "smart"}, read_only=True, idempotent=True)
_register(list_orphans, title="List orphaned documents", tags={"read", "smart"}, read_only=True, idempotent=True)

# Export
_register(export_pdf, title="Export document as PDF", tags={"read", "export"}, read_only=True, idempotent=True)


# --- Resources: fetch-once reference data ---------------------------------
_SQL_SCHEMA = """\
SiYuan internal SQLite schema (read-only via siyuan_sql_query).

Tables and key columns:
  blocks      id, parent_id, root_id, box, path, hpath, name, content,
              markdown, type, subtype, sort, created, updated
  spans       id, block_id, content, type   (e.g. 'tag', 'a')
  refs        id, block_id, def_block_id, content, type
  attributes  id, block_id, name, value

Block type codes (blocks.type):
  d  document     h  heading       p  paragraph    l  list
  i  listItem     c  code          m  math         t  table
  s  superBlock   b  blockquote

Heading level lives in blocks.subtype ('h1'..'h6'); task checkboxes are
list-items (type='i') with subtype 't' (open) or 'd' (done).

Conventions:
  - box  = notebook ID            - hpath = human path, e.g. /Projects/Foo
  - Only SELECT is permitted; a LIMIT is auto-appended if omitted (max 200 rows).

Example:
  SELECT id, content FROM blocks WHERE content LIKE '%TODO%' LIMIT 10
"""


@mcp.resource(
    "siyuan://schema",
    name="SiYuan SQL schema",
    description="Column legend + block-type codes for siyuan_sql_query.",
    mime_type="text/plain",
    tags={"reference"},
)
def schema_resource() -> str:
    """Authoritative SQL cheat-sheet — fetch once instead of re-reading docstrings."""
    return _SQL_SCHEMA


@mcp.resource(
    "siyuan://notebooks",
    name="SiYuan notebooks",
    description="Live list of notebooks (id, name, closed) in the workspace.",
    mime_type="application/json",
    tags={"reference"},
)
async def notebooks_resource() -> list[dict]:
    """Live notebook catalog so the model resolves IDs without a tool call."""
    return await list_notebooks()


@mcp.resource(
    "siyuan://doc/{doc_id}/outline",
    name="SiYuan document outline",
    description=(
        "Heading-only outline (id, content, level, sort) for a document, "
        "addressed by its block ID. Mirrors siyuan_get_document_outline."
    ),
    mime_type="application/json",
    tags={"reference", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def doc_outline_resource(doc_id: str) -> str:
    """Resource-template view of a document's heading outline.

    Reuses ``get_document_outline`` so the resource and the tool stay in lockstep.
    Pure read — never mutates. Error-path-safe: an invalid/unsafe ``doc_id`` or a
    kernel hiccup yields a single ``[{"error": ...}]`` row instead of raising, so
    a client resource-read degrades to a readable JSON payload rather than a
    transport fault.

    Returns a JSON-encoded array of heading rows (id, content, level, sort) so
    the whole outline is one ``application/json`` document.
    """
    try:
        headings = await get_document_outline(doc_id)
        rows = [h.model_dump() for h in headings]
    except Exception as exc:  # ValueError (unsafe id), SiYuanError, transport, ...
        logger.info("doc_outline_resource failed for %r: %s", doc_id, exc)
        rows = [OutlineHeading(error=str(exc)).model_dump()]
    return json.dumps(rows, default=str)


@mcp.resource(
    "siyuan://status",
    name="SiYuan sidecar status",
    description="Server version, transport, and cached upstream-kernel reachability.",
    mime_type="application/json",
    tags={"reference"},
)
async def status_resource() -> dict:
    """Lightweight status snapshot for orientation (uses the cached probe)."""
    upstream_ok = await _probe_upstream()
    return {
        "service": "mcp-siyuan",
        "version": __version__,
        "transport": settings.transport,
        "upstream_reachable": upstream_ok,
        "uptime_seconds": int(
            (datetime.now(timezone.utc) - _start_time).total_seconds()
        ),
    }


# --- Prompts: guided multi-step workflows ---------------------------------
@mcp.prompt(
    name="daily_review",
    description="Review recent documents and open tasks, then summarize next actions.",
    tags={"workflow"},
)
def daily_review_prompt(notebook: str = "", days: int = 7) -> str:
    """Guided daily review combining get_recent_docs + find_tasks."""
    scope = f" in notebook {notebook}" if notebook else " across all notebooks"
    nb_arg = f', notebook="{notebook}"' if notebook else ""
    return (
        f"Run a daily review{scope}.\n\n"
        f"1. Call siyuan_get_recent_docs(limit=10{nb_arg}) to see what was "
        "touched recently.\n"
        f"2. Call siyuan_find_tasks(checked=False, days={days}{nb_arg}) to list "
        "open TODOs; each item carries its parent doc_title.\n"
        "3. Summarize: group open tasks by document, flag anything stale or "
        "high-priority, and propose a short ordered list of next actions.\n"
        "4. Do NOT modify anything unless the user asks — this is a read-only review."
    )


@mcp.prompt(
    name="process_inbox",
    description="Walk an inbox/notebook, summarize each recent doc, and propose routing.",
    tags={"workflow"},
)
def process_inbox_prompt(notebook: str, limit: int = 10) -> str:
    """Guided inbox processing over a single notebook."""
    nb_quoted = '"' + notebook + '"'
    return (
        f"Process the inbox notebook {notebook} (up to {limit} most-recent docs).\n\n"
        f"1. Call siyuan_get_recent_docs(limit={limit}, notebook={nb_quoted}).\n"
        "2. For each document, read it with siyuan_get_document(id=...) and write a "
        "one-line summary.\n"
        "3. Extract any action items with siyuan_find_tasks or by reading checkboxes; "
        "for genuinely new actions, propose siyuan_capture_task calls (do not run them "
        "until the user confirms).\n"
        "4. Propose a destination for each doc (keep / file under a project / archive) "
        "and, only on confirmation, use siyuan_move_doc to file it.\n"
        "5. Present the summary as a table: document, summary, open actions, proposed route."
    )


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
