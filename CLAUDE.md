# CLAUDE.md

Guidance for Claude Code in this repository. The README is the full reference (tool catalog, runbook, conventions); this file holds what to know before changing code.

## Commands

```bash
uv sync                  # install (incl. dev group)
uv run pytest            # full suite; tests/test_readme_tool_catalog.py keeps the README catalog in sync
uv run ruff check .      # lint (CI gate)
```

## fastmcp 4 idioms

- Fleet conventions (tag-only releases, bearer `MCP_API_KEY` behind the Cloudflare portal, usage telemetry, long-job pattern): `CDiT-infrastructure/docs/wiki/topics/mcp-fleet.md`.
- Tests: the `mcp-testing` skill (in-memory `Client(mcp)`, protocol surface, post-deploy smoke).
- Release/deploy workflow changes: the `cdit-release-pipeline` skill. Releases are tags; `pyproject.toml`'s version is static and lags them.
- `main` is protected: branch, PR, the `test` check must pass. A merge to `main` is the deploy (Komodo stack `git-mcp-siyuan-nebula`, build from source).
- No `ctx.info` / progress events: the portal forwards nothing server-to-client.
- `usage.py` is vendored unchanged into every fleet server; do not fork it here.

## SiYuan gotchas

- **The SQL index lags writes.** A document created through the API may not appear in `/api/query/sql` or search for a long time (observed ~1 h). Read structure from the kernel (`getChildBlocks`, as `get_block_children` and `get_document_outline` do), never from SQL, right after a write; an SQL-based existence check on a fresh doc will miss it and duplicate content.
- **`/health` can be falsely healthy.** It probes the unauthenticated `/api/system/bootProgress`, so a stale `SIYUAN_TOKEN` passes health while every tool 401s. Test auth with a token-required endpoint (`/api/notebook/lsNotebooks`).
- **Single replica only.** The idempotency replay cache and the diag ring buffer are per-process.
