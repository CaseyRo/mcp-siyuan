## Context

`mcp-siyuan` is a FastMCP 3.x Python sidecar exposing the SiYuan kernel API as MCP tools, deployed via Komodo (`km` CLI) on Hetzner behind the Cloudflare MCP Portal at `mcp.cdit-dev.de`. Clients reach it through Cloudflare Tunnel + Access, then through a portal aggregator, then to this server, which calls SiYuan over HTTP.

Failure mode under investigation: tool calls intermittently return the literal string `No approval received.` for several consecutive identical invocations, then succeed unchanged on retry. The same string appears on unrelated upstream MCP servers (Things). It is **not** produced by this server's code — confirmed by source grep — so the failure originates in a shared upstream layer (Cloudflare MCP Portal, FastMCP framework approval semantics, or Claude.ai client connector behavior). This server has no diagnostic surface to confirm whether failed calls reached it, which is the gap this change closes.

Adjacent state in this repo:

- FastMCP `==3.2.4` was pinned in commit `0a91f8e` along with `stateless_http`, a `/health` endpoint, and fail-fast auth on startup.
- Existing `/health` endpoint returns a static OK; no request log surface.
- No structured logging today — stdlib `logging` is used with default text formatter.
- Single-replica deploy on Komodo; no horizontal scaling.
- Tool registration uses FastMCP decorators in `src/mcp_siyuan/tools/`.

Stakeholders: Casey (operator/maintainer), CDIT MCP fleet consumers (Claude Desktop, Claude.ai connectors, n8n, Claude Code), and the Stolperstein knowledge base (`ku_494ce33c05e27731d2f4d9813e10100b`).

## Goals / Non-Goals

**Goals:**

- Make every tool invocation observable end-to-end via a correlation ID that can be matched against portal, Cloudflare Access, and SiYuan kernel logs.
- Make client-side retry of write tools safe by default (no duplicate documents/blocks under `No approval received.`-class failures).
- Pin FastMCP exactly so the framework version is a fixed variable in the upstream investigation.
- Convert the README into the canonical reference for tool consumers and operators.
- Ship without new infrastructure dependencies (no Redis, no central log store, no schema migrations).

**Non-Goals:**

- Root-cause fixing the `No approval received.` bug. That work lives in the portal repo and/or FastMCP framework — see proposal "out-of-scope investigation tasks."
- Distributed/multi-replica deployment. The idempotency cache is in-process and per-instance; horizontal scaling of `mcp-siyuan` would invalidate that assumption and is explicitly out of scope.
- Replacing FastMCP or changing transport (streamable HTTP + stdio stays).
- New tools or capabilities beyond observability and idempotency.
- Auth/authz changes — CF Access in front stays as the access boundary.

## Decisions

### 1. Correlation ID middleware

A FastMCP server-level middleware (or, if the framework version exposes no middleware hook, a thin decorator wrapping every registered tool function) generates a UUIDv4 per invocation and stores it in a `contextvars.ContextVar` so any code under the call can read it for log lines and error messages.

**Why**: `contextvars` is async-safe and stdlib — no thread-local pitfalls, no extra dependency. Generating server-side rather than trusting an inbound `X-Correlation-ID` keeps the ID format consistent and avoids a malformed-header attack surface; if the portal later passes one in, we can chain it as `parent_request_id`.

**Alternatives considered**: (a) Trust an inbound header — rejected because the portal doesn't currently send one and we'd be debugging two formats. (b) `ContextVar` per task in `asyncio` — same thing, we're using it. (c) Pass `request_id` explicitly through every function signature — invasive, breaks tool decorator ergonomics.

### 2. Structured logging via stdlib `logging` + custom JSON formatter

Replace the default formatter with a `json.dumps`-based formatter that emits one JSON object per log record with fields: `ts`, `level`, `request_id`, `tool_name`, `caller`, `args_size_bytes`, `kernel_status`, `latency_ms`, `outcome`, `message`. Configurable via env var `SIYUAN_LOG_LEVEL`.

**Why**: Avoids adding `structlog` (small dep but unnecessary for a single small server). Stdlib `logging` is what the rest of the codebase already uses. JSON shape is greppable and parseable by Komodo log viewer / `jq`.

**Alternatives considered**: `structlog` — better ergonomics for context binding but adds a dep for marginal gain. `loguru` — same trade-off, opinionated and we don't need its features.

### 3. Idempotency cache: in-process `cachetools.TTLCache`

Add `cachetools` as a dependency. Use a single `TTLCache(maxsize=1024, ttl=SIYUAN_IDEMPOTENCY_TTL_SECONDS)` shared across the five write tools. Key: `(tool_name, idempotency_key)`. Value: the serialized tool result. Only **successful** results are cached — kernel errors are NOT cached so retries after a real failure can succeed.

**Why**: Smallest possible change. `cachetools` is a tiny well-maintained pure-Python lib; its `TTLCache` is thread-safe-enough for our async single-process use. Bounded by `maxsize` so a misbehaving client can't OOM us.

**Alternatives considered**: (a) Hand-rolled dict with a TTL sweep — reinventing the wheel. (b) Redis-backed cache — requires infra change; rejected as overscoped, but documented as the migration path if we ever scale horizontally. (c) `functools.lru_cache` — no TTL.

**Critical semantics**: Caching only on success means a transient `No approval received.` failure (which the proposal hypothesizes is upstream of this server) won't poison the cache; the next retry runs the kernel call fresh.

### 4. `/health?diag=1` ring buffer

A `collections.deque(maxlen=SIYUAN_DIAG_BUFFER_SIZE)` shared across the process, appended to on every tool call's exit log. `/health?diag=1` serializes the buffer to JSON. The endpoint stays behind whatever auth the existing `/health` endpoint uses (which, per the recent reliability commit, is fail-fast auth-gated).

**Why**: Trivially cheap, no external dep, gives ad-hoc cross-system tracing without standing up a log shipper. The deque's `maxlen` makes memory bounded.

**Alternatives considered**: Ship logs to Loki/Promtail — out of scope; we don't have that infra and it'd block this change. File-based ring buffer — disk noise, harder to read remotely.

### 5. FastMCP version pinning + startup assertion

Change `pyproject.toml` from `fastmcp>=3.2.4,<4` to `fastmcp==3.2.4`. Add a startup check that imports `fastmcp.__version__` and logs it; fail loud (do not crash) if it doesn't match the expected pin.

**Why**: The investigation needs FastMCP to be a known-fixed variable. A loose range means a `pip install` two months from now could shift the framework underneath us and confuse the bisect.

**Alternatives considered**: Don't pin (status quo) — leaves us debugging a moving target. Vendor FastMCP — far too invasive.

### 6. Tool catalog: hand-written, validated by introspection test

The README tool catalog is hand-written Markdown with one row per tool. A test in `tests/test_readme_tool_catalog.py` introspects the FastMCP server's registered tools and asserts every registered tool name appears in the README. Drift fails CI.

**Why**: Hand-written reads better (one-line descriptions need editorial care), but the test catches the "added a tool, forgot to document" failure mode without requiring auto-gen tooling that couples README format to FastMCP internals.

**Alternatives considered**: Pure auto-generation — readable output is harder; fragile across FastMCP versions. Pure hand-write with no test — drifts within two release cycles.

### 7. Architecture diagram: Mermaid in the README

Use a Mermaid diagram (GitHub renders it natively) for the request flow: `Claude → Cloudflare Access → MCP Portal → mcp-siyuan → SiYuan kernel`.

**Why**: Source-controllable, no PNG management, edits are diffable. GitHub and PyPI both render Mermaid in Markdown.

**Alternatives considered**: ASCII diagram — uglier and harder to evolve. PNG — requires checked-in binary and a separate edit workflow.

### 8. Idempotency key shape and validation

`idempotency_key` is an optional `str | None` field on each write tool's argument model. If provided, MUST be a non-empty string ≤128 chars matching `^[A-Za-z0-9_\-:.]+$`. Invalid keys raise a validation error before any kernel call.

**Why**: Conservative validation prevents silly mistakes (whitespace, control chars) and bounds key memory. Char set permits UUIDs, request IDs, and human-readable keys like `funkstrecke-2026-04-29`.

## Risks / Trade-offs

- **In-process idempotency cache breaks under multi-replica deploy.** → Documented as single-replica-only in README. CI enforcement is impractical here; we rely on operator discipline. If we ever scale, swap `cachetools.TTLCache` for a Redis client behind the same interface.
- **Diag endpoint leaks recent activity to anyone with CF Access.** → Same trust boundary as the rest of the API; CF Access already gates who can call this server. Documented in README.
- **JSON logs are less human-readable in `docker logs` tailing.** → Pipe through `jq` in the runbook section. Trade-off accepted: machine-parseable wins over eyeball-friendly because the whole point is cross-system correlation.
- **Pinning FastMCP to `==3.2.4` blocks security patches until we explicitly bump.** → Acceptable for a 2–4 week investigation window. Add a `# TODO: revisit after No-approval-received RCA` comment next to the pin so it doesn't ossify.
- **Hand-written tool catalog drifts.** → Mitigated by the introspection test in (6).
- **Idempotency key collision across clients sharing the same key value.** → Cache key is `(tool_name, idempotency_key)`; not cross-tool. If two clients pick the same key for the same tool within the TTL, the second gets the first's result. Documented as a client-responsibility caveat; recommend UUID or namespace prefixes.

## Migration Plan

1. Merge to `main`. Komodo `km` deploy picks up the build automatically (existing git-push workflow).
2. Watch the next 24h of logs for the new JSON shape; confirm `request_id` is present on every tool call.
3. Backfill the README runbook with one real `request_id` from a successful diag pull.
4. **Rollback**: revert the merge commit; Komodo redeploys the prior image. No data migration to undo. Idempotency cache is in-memory so it's just gone.

## Open Questions

- Should `idempotency_key` default to a hash of (tool_name + serialized args) when omitted, giving "free" idempotency for clients that don't pass one? **Tentative answer: no.** That changes write semantics in a non-obvious way; clients that legitimately want to create two identical documents in the same TTL would be surprised. Stay opt-in.
- Should the diag endpoint live at `/health?diag=1` or at a separate `/diag` path? **Tentative answer: the query-param form**, because it reuses the existing health endpoint's auth and avoids a new route registration. Open to flipping if FastMCP makes that ugly.
- Should we emit a Komodo-side log alert when `outcome=error` rate exceeds a threshold? **Out of scope** for this change — but worth noting that the JSON log shape makes this a 5-minute follow-up.
