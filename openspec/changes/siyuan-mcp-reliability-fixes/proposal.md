## Why

`mcp-siyuan` tool calls intermittently return the literal error string `No approval received.` — five consecutive identical `siyuan_create_document` calls failed with that string on 2026-04-29, then a sixth byte-identical retry returned a real block ID with no input change, no backoff, and the same MCP session. The same string has been observed on unrelated upstream MCP servers (Things) in the same conversation, which means the failure originates in a shared layer (Cloudflare MCP Portal, FastMCP framework, or Claude.ai client) — not in this server's code. However, this server has **no diagnostic surface** to confirm that: we cannot tell whether failed calls reached the SiYuan kernel, were rejected upstream, or were dropped before entering our request handler. Without that signal, root-causing the bug across `mcp.cdit-dev.de` is guesswork.

Stolperstein KU `ku_494ce33c05e27731d2f4d9813e10100b` documents the symptom and a manual retry workaround. Related KU `ku_9acd350f95e2190c00cc364250976c55` covers portal caching. Adjacent work: CDI-821 (server consolidation), CDI-948/949 (portal auth and `mcp-infra` spec).

## What Changes

- **Per-request correlation IDs** — every tool invocation gets a UUID logged at request entry and exit, surfaced in error responses so failed calls can be matched against portal logs, Cloudflare Access logs, and SiYuan kernel logs.
- **Structured request/response logging** — JSON log line per tool call with `request_id`, `tool_name`, `caller` (extracted from CF Access JWT if present), arg sizes, kernel response code, latency, and outcome. Distinguishes "request never reached this server" from "this server returned an error".
- **Write-tool idempotency keys** — `siyuan_create_document`, `siyuan_append_block`, `siyuan_insert_block`, `siyuan_update_block`, and `siyuan_set_block_attrs` accept an optional `idempotency_key`. A short-lived in-process cache (default 5 min) returns the prior result on key replay, so a client retrying after `No approval received.` cannot accidentally create duplicate documents/blocks.
- **FastMCP version audit** — pin and document the exact FastMCP version (currently 3.2.4 per recent commit). Add a `pyproject.toml` upper bound and a smoke test that asserts the version at startup. The investigation hypothesis space includes "FastMCP framework misfiring approval semantics" — pinning makes that question answerable.
- **`/health` extension to `/health?diag=1`** — when query parameter is set, return the last N (default 50) request log entries as JSON. Auth-gated by the existing CF Access layer. Cheaper than shipping logs to a central store for a small server.
- **Major README expansion** — the current README is minimal; this change rewrites it as the canonical operator/integrator reference. Sections:
  - **Overview**: what `mcp-siyuan` is, what SiYuan is, and the sidecar architecture (this server runs alongside the SiYuan kernel and exposes its API as MCP tools).
  - **Tool catalog**: every tool grouped by tier (read/query, write, export, move/rename) with one-line descriptions, argument shapes, and a representative example. Generated or hand-written but kept in sync with the registered tools.
  - **Transport architecture**: why we use FastMCP 3.x with **streamable HTTP** for remote clients (Claude Desktop, Claude.ai connectors, n8n) and **stdio** for local Claude Code. Brief contrast with the older HTTP+SSE transport pattern and why streamable HTTP is the current MCP standard. Diagram of request flow: Claude → Cloudflare Access → CF MCP Portal → `mcp-siyuan` → SiYuan kernel.
  - **FastMCP usage notes**: the patterns this repo uses — tool registration via decorators, Pydantic arg models, `stateless_http`, `/health` endpoint, fail-fast auth on startup. Pointers to FastMCP docs rather than re-documenting the framework.
  - **Configuration**: full env-var table (SiYuan kernel URL/token, CF Access, log level, diag buffer, idempotency TTL, etc.) with defaults and which deploy target sets each one.
  - **Deployment**: Komodo / `km` CLI git-push workflow, Docker image structure, sidecar `docker-compose` pattern, and how this fits into the broader CDIT MCP fleet (`mcp.cdit-dev.de`).
  - **Operator runbook**: the observed `No approval received.` pattern, portal-layer hypothesis, manual-retry workaround (retry once, never commit destructive downstream ops until a real success return), correlating `request_id` across portal / CF Access / kernel logs, and the new `/health?diag=1` endpoint.
  - **Local development**: running stdio mode against a local SiYuan, running streamable HTTP mode behind a tunnel, smoke tests.
  - **Versioning and release**: how `__init__.__version__` syncs with `pyproject.toml`, the chore release commit pattern.
- **Investigation issue list** (out-of-scope for this repo, tracked in proposal): grep portal/FastMCP source for the literal string, pull CF Access logs at failure timestamps, reproduce with `curl` directly against `mcp.cdit-dev.de`, audit per-call approval gating in portal config.

This change is **non-breaking**: idempotency keys are optional, logging is additive, the diag endpoint is opt-in via query param.

## Capabilities

### New Capabilities

- `request-observability`: Correlation IDs, structured per-request logging, and an opt-in diagnostic endpoint for cross-system request tracing.
- `write-idempotency`: Optional idempotency-key handling for write tools, with an in-process replay cache and documented semantics for client retry behavior under `No approval received.`-class failures.

### Modified Capabilities

<!-- No main specs exist yet (scaffold-fastmcp-server still in-flight). Once it archives, future changes may move idempotency hooks into write-tools as a delta. -->

## Impact

- **Code**:
  - New middleware/decorator wrapping every tool invocation for correlation ID + structured log
  - New small in-process LRU cache module for idempotency keys (TTL-based)
  - Modifications to the five write tool handlers to read/write the idempotency cache
  - `/health` endpoint extension
- **Dependencies**: No new runtime deps. May add `structlog` or use stdlib `logging` with a JSON formatter. Pin FastMCP to `==3.2.4` (or current) with documented upper bound.
- **Configuration**: New env vars — `SIYUAN_LOG_LEVEL` (default `INFO`), `SIYUAN_DIAG_BUFFER_SIZE` (default `50`), `SIYUAN_IDEMPOTENCY_TTL_SECONDS` (default `300`).
- **Operations**: Komodo stack picks up the changes via existing git-push deploy (`km` workflow). No infra changes needed.
- **Documentation**: `README.md` grows from a stub to the canonical reference (~est. 300–600 lines including the tool catalog table). No new doc directory; everything stays in `README.md` so it renders on GitHub and PyPI without extra tooling.
- **Cross-repo / out-of-scope investigation tasks** (will be filed against the appropriate repos once this change ships, *not* tracked under this OpenSpec change):
  - Grep `klartext` portal source and FastMCP source for `"No approval received"` to locate origin
  - Pull Cloudflare Access logs for `mcp.cdit-dev.de` around failure timestamps
  - `curl`-reproduce against `mcp.cdit-dev.de` with the same bearer token Claude uses
  - Audit per-call approval/consent gating in portal and Claude.ai connector config
- **Linear**: Stolperstein KU `ku_494ce33c05e27731d2f4d9813e10100b`. CDI-821 / CDI-948 / CDI-949 are adjacent but not blockers.
