## Context

SiYuan Notes exposes a kernel HTTP API at port 6806 with POST-based JSON endpoints for notebooks, blocks, documents, SQL queries, and attributes. Auth is via `Authorization: Token <token>` header. All responses follow `{ code: 0, msg: "", data: ... }` envelope.

No maintained MCP server exists for SiYuan. We build one from scratch using FastMCP 3.x (Python), which provides decorator-based tool registration and native support for both stdio and streamable HTTP transports.

The server runs as a sidecar Docker container alongside SiYuan on Hetzner, deployed via Komodo (`km` CLI) with git-push triggers.

## Goals / Non-Goals

**Goals:**
- Expose SiYuan read/query/write operations as MCP tools consumable by Claude Desktop, Claude Code, and n8n
- Single Python package installable via `pip install mcp-siyuan` or runnable as Docker sidecar
- Dual transport: streamable HTTP (`:8000/mcp`) for network clients, stdio for Claude Code local use
- Clean separation: SiYuan HTTP client module → tool modules → FastMCP server entry point
- Config via environment variables (`SIYUAN_URL`, `SIYUAN_TOKEN`)

**Non-Goals:**
- Tier 3 PreCog tools (freeze/thaw) — blocked on PreCog attribute schema
- Tier 4 housekeeping tools (delete, move, rename, snapshot) — stretch, separate change
- WebSocket/real-time sync — SiYuan kernel doesn't support it for external clients
- Auth/RBAC on the MCP server itself — runs in trusted sidecar network
- UI or web frontend

## Decisions

### D1: FastMCP 3.x with decorator-based tools
**Choice:** FastMCP 3.x (`from fastmcp import FastMCP`) with `@mcp.tool` decorators.
**Why:** Native streamable HTTP + stdio, Pydantic model integration, minimal boilerplate. The `mcp.run(transport="http", host="0.0.0.0", port=8000)` pattern handles transport selection at startup.
**Alternative:** Raw `mcp` SDK — requires manual server/transport wiring, more code for same result.

### D2: httpx async client for SiYuan API
**Choice:** `httpx.AsyncClient` with connection pooling for all SiYuan kernel calls.
**Why:** FastMCP tools are async. httpx is the standard async HTTP client in Python. Connection pooling avoids per-request overhead to sidecar-local SiYuan.
**Alternative:** `aiohttp` — heavier dependency, less ergonomic for JSON APIs.

### D3: Pydantic models for request/response validation
**Choice:** Pydantic v2 models for SiYuan API responses and MCP tool parameters.
**Why:** FastMCP uses Pydantic natively for tool parameter schemas. Validates SiYuan responses, catches API changes early.
**Alternative:** Raw dicts — fragile, no auto-generated MCP schemas.

### D4: Project structure
```
mcp_siyuan/
├── __init__.py
├── server.py          # FastMCP instance, transport entry point
├── client.py          # SiYuan kernel HTTP client (httpx)
├── config.py          # Settings from env vars (pydantic-settings)
├── models.py          # Pydantic models for SiYuan types
├── tools/
│   ├── __init__.py
│   ├── read.py        # Tier 1: list_notebooks, sql_query, get_document, search, get_block, get_block_attrs
│   └── write.py       # Tier 2: create_document, update_block, insert_block, append_block, set_block_attrs, daily_note
├── py.typed
Dockerfile
docker-compose.sidecar.yml
pyproject.toml
```
**Why:** Flat module layout, tools split by read/write concern. `server.py` is the entry point for both transports.

### D5: Transport selection via CLI/env
**Choice:** `TRANSPORT=http` (default in Docker) or `TRANSPORT=stdio` (default in local/CLI). Server reads env var and calls `mcp.run(transport=...)`.
**Why:** Same codebase serves both use cases. Docker compose sets `TRANSPORT=http`; Claude Code config uses stdio.

### D6: Docker sidecar on shared network
**Choice:** Sidecar container in same docker-compose as SiYuan, shared bridge network. SiYuan reachable at `http://siyuan:6806`.
**Why:** No port exposure needed for SiYuan kernel. Sidecar pattern matches existing CDIT Docker architecture. Komodo deploys the full stack via git push.

### D7: uv for dependency management
**Choice:** `uv` with `pyproject.toml` for deps, lockfile, and build.
**Why:** Fast, standard, already used in CDIT Python projects. `uv run` for dev, `uv pip install` in Docker.

## Risks / Trade-offs

- **SiYuan API instability** → Pin to SiYuan kernel version tested against; model validation catches breaking changes early
- **Large document content** → `get_document` may return very large markdown strings; add `max_length` parameter with sensible default to truncate for LLM context windows
- **SQL injection via sql_query tool** → SiYuan's SQL endpoint is read-only on its SQLite DB; document this clearly in tool description but don't add artificial restrictions that break legitimate queries
- **No auth on MCP endpoint** → Acceptable in sidecar network; document that external exposure requires a reverse proxy with auth
