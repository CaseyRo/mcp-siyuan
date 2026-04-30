## 1. Foundations

- [x] 1.1 Add `cachetools` to `pyproject.toml` runtime deps
- [x] 1.2 Pin `fastmcp` to exact version `==3.2.4` in `pyproject.toml` (with a comment referencing the No-approval-received RCA so it isn't accidentally relaxed)
- [x] 1.3 Add new env-var schema entries: `SIYUAN_LOG_LEVEL` (default `INFO`), `SIYUAN_DIAG_BUFFER_SIZE` (default `50`), `SIYUAN_IDEMPOTENCY_TTL_SECONDS` (default `300`)
- [x] 1.4 Lock-file refresh and local install verification

## 2. Correlation ID + Context

- [x] 2.1 Create `mcp_siyuan/observability/context.py` with a `request_id` `ContextVar[str | None]` and helpers `set_request_id()`, `get_request_id()`
- [x] 2.2 Pick the integration point: chose `@traced_tool` decorator wrapping every registered tool function (FastMCP 3.2.4 has no clean middleware hook for this)
- [x] 2.3 Generate a UUIDv4 at request entry, store it in the ContextVar, expose it to error handlers
- [x] 2.4 Ensure error responses returned to MCP clients carry `request_id` (appended to exception args[0] so it surfaces in the FastMCP error payload)
- [x] 2.5 Unit test: concurrent invocations see distinct IDs in their own context (use `asyncio.gather` with two slow tool stubs)

## 3. Structured JSON Logging

- [x] 3.1 Create `mcp_siyuan/observability/logging_setup.py` with a JSON formatter that emits `ts`, `level`, `request_id`, `tool_name`, `caller`, `args_size_bytes`, `kernel_status`, `latency_ms`, `outcome`, `message`
- [x] 3.2 Wire the formatter into the root logger at server startup; honor `SIYUAN_LOG_LEVEL`
- [x] 3.3 In the tool wrapper from 2.2, emit an entry log on call start and an exit log on call end with all fields populated
- [x] 3.4 Extract `caller` from the bearer-token verifier (sets `caller="bearer"` on successful auth); CF Access JWT subject extraction is documented as a future enhancement once the portal forwards the header
- [x] 3.5 Compute `args_size_bytes` as `len(json.dumps(args).encode("utf-8"))` (best-effort; on serialization failure, log `null`)
- [x] 3.6 Set `outcome` to one of `success`, `error`, `validation_error`; set `kernel_status` from the SiYuan response code (via ContextVar set in `client.py`) or `null` if the call never reached the kernel
- [x] 3.7 Unit test: JSON formatter produces parseable output containing all required fields
- [x] 3.8 Unit test: validation-error path emits `outcome=validation_error` and `kernel_status=null`

## 4. Diagnostic Endpoint

- [x] 4.1 Create `mcp_siyuan/observability/diag_buffer.py` exposing a process-global `collections.deque` with `maxlen=SIYUAN_DIAG_BUFFER_SIZE`
- [x] 4.2 Append every exit log record to the deque (alongside the regular log emission)
- [x] 4.3 Extend the existing `/health` route to read the `diag` query param; when `diag=1` is present, serialize the deque snapshot to JSON
- [x] 4.4 Confirm the `/health` route's existing auth gate also covers the diag form (no separate auth path) — `mcp.custom_route` reuses the FastMCP server's auth chain
- [x] 4.5 Integration test: call `GET /health?diag=1` after a series of tool invocations and assert the response contains the expected request IDs in order

## 5. Idempotency Cache

- [x] 5.1 Create `mcp_siyuan/idempotency/cache.py` with a singleton `cachetools.TTLCache(maxsize=1024, ttl=SIYUAN_IDEMPOTENCY_TTL_SECONDS)` and a small wrapper exposing `get(tool_name, key)`, `put(tool_name, key, value)`, and `with_idempotency()`
- [x] 5.2 Define an `idempotency_key: str | None = None` parameter on each of the five write tools with validator `^[A-Za-z0-9_\-:.]+$` and length 1..128 (validated by `cache.validate_key()`; tools are plain async functions, not Pydantic models)
- [x] 5.3 In each of the five write-tool handlers, if `idempotency_key` is set: lookup the cache; on hit return the cached value; on miss invoke the kernel and on success store the result; on any kernel error or exception do NOT store (handled by `with_idempotency` helper — failures propagate without writing)
- [x] 5.4 Add explicit log lines for cache `hit` / `miss` (so the diag endpoint shows when retries were absorbed); `skip-error` is implicit because the failure path raises before `put()` is reached
- [x] 5.5 Unit test: replay within TTL returns cached value without calling the kernel (mock the kernel client)
- [x] 5.6 Unit test: replay after TTL expiry calls the kernel again
- [x] 5.7 Unit test: kernel error does not write a cache entry (subsequent identical call with same key calls the kernel again)
- [x] 5.8 Unit test: same key on two different tools (`create_document` vs `append_block`) does NOT collide
- [x] 5.9 Unit test: invalid `idempotency_key` (empty, too long, bad chars) raises validation error before any kernel call

## 6. FastMCP Version Audit

- [x] 6.1 At server startup, import `fastmcp.__version__` and emit an INFO log record with field `fastmcp_version`
- [x] 6.2 Compare the imported version to the pin from `pyproject.toml`; if mismatch, emit ERROR log line naming both versions but do NOT raise
- [x] 6.3 Unit test: version-mismatch path logs ERROR and returns normally

## 7. README Expansion

- [x] 7.1 Replace stub `README.md` with the new structure: Overview, Tool Catalog, Transport Architecture (with Mermaid diagram), FastMCP Usage Notes, Configuration, Deployment, Operator Runbook, Local Development, Versioning & Release
- [x] 7.2 Write the Tool Catalog table by hand: one row per registered tool with name, tier, one-line description, primary args, and a representative example invocation
- [x] 7.3 Add Mermaid diagram of the request flow `Claude → Cloudflare Access → MCP Portal → mcp-siyuan → SiYuan kernel`
- [x] 7.4 Document the streamable-HTTP vs stdio transport choice, with brief contrast to the older HTTP+SSE pattern, and link to FastMCP docs
- [x] 7.5 Document every env var introduced by this change and every existing one; mark which deploy target sets each
- [x] 7.6 Write the Operator Runbook section: the `No approval received.` symptom, the portal-layer hypothesis, the manual-retry workaround, how to correlate `request_id` across portal / CF Access / kernel logs, the new `/health?diag=1` endpoint usage with `curl` examples, and a `jq` recipe for filtering JSON logs
- [x] 7.7 Document the single-replica constraint of the in-process idempotency cache
- [x] 7.8 Document the FastMCP exact-pin and the rationale (link to this change)
- [x] 7.9 Add a Local Development section covering stdio mode against a local SiYuan, streamable-HTTP mode behind a tunnel, and how to run smoke tests
- [x] 7.10 Add a Versioning & Release section explaining the `__init__.__version__` ↔ `pyproject.toml` sync pattern observed in commit `8f82d78`

## 8. README Drift Test

- [x] 8.1 Create `tests/test_readme_tool_catalog.py` that imports the FastMCP server, enumerates registered tool names, and asserts every name appears literally in `README.md`
- [x] 8.2 Wire that test into the default test suite so CI fails on drift (lives under `tests/` which is the configured `testpaths` in pyproject.toml — picked up by default)
- [x] 8.3 Run the test locally and fix any drift surfaced by tools introduced before this change (catalog covers all 29 registered tools; test passes)

## 9. Documentation of Investigation Hand-offs

- [x] 9.1 In the README runbook, list the cross-repo investigation tasks as "next steps once a `request_id` is in hand" — grep portal/FastMCP source for `"No approval received"`, pull CF Access logs, `curl`-reproduce against `mcp.cdit-dev.de`, audit per-call approval gating
- [ ] 9.2 Update the Stolperstein KU `ku_494ce33c05e27731d2f4d9813e10100b` to reference this change and the new `/health?diag=1` endpoint as the recommended diagnostic surface (writes to external system — deferred for user confirmation)

## 10. Verification & Release

- [x] 10.1 Run the full test suite locally (`uv run pytest`) and confirm green — 129 passed, 6 skipped (PDF tests requiring optional deps), no regressions
- [ ] 10.2 Build the Docker image locally and confirm startup logs contain `fastmcp_version` and the formatter emits JSON (deferred — local docker build, run when ready to ship)
- [ ] 10.3 Run a manual smoke test: call a read tool and a write tool over streamable HTTP, then `GET /health?diag=1` and confirm both calls show up in the buffer with distinct `request_id`s (deferred — needs running server)
- [x] 10.4 Run `openspec validate --change siyuan-mcp-reliability-fixes` and resolve any issues — `Change 'siyuan-mcp-reliability-fixes' is valid`
- [x] 10.5 Bump `__init__.__version__` to 0.2.5 in this commit; the release CI auto-bumps `pyproject.toml` PATCH on merge to main, so both end up at 0.2.5 in sync
- [x] 10.6 Open PR against `main` — https://github.com/CaseyRo/mcp-siyuan/pull/10 (+1748 / −68 across 41 files); on merge, release CI tags v0.2.5, builds the Docker image to ghcr.io, then Komodo picks up the new image
- [ ] 10.7 Post-deploy: pull a fresh `request_id` from `/health?diag=1` and paste it into the README runbook example so the docs reference real data (deferred — requires merge + deploy first)
