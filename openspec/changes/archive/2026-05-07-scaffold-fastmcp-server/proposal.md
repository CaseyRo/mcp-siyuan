## Why

There is no maintained, production-quality MCP server for SiYuan Notes. Existing TypeScript implementations (onigeya, porkll, xgq18237) are stale, AI-generated, or missing HTTP transport — none use FastMCP. We need a Python MCP server on FastMCP 3.x so Claude Desktop, Claude Code, and n8n can read, query, and write SiYuan content over streamable HTTP and stdio.

## What Changes

- New Python package `mcp-siyuan` built on FastMCP 3.x
- SiYuan kernel HTTP client wrapping the `/api/*` endpoints
- **Tier 1 Read/Query tools**: `siyuan_list_notebooks`, `siyuan_sql_query`, `siyuan_get_document`, `siyuan_search`, `siyuan_get_block`, `siyuan_get_block_attrs`
- **Tier 2 Write tools**: `siyuan_create_document`, `siyuan_update_block`, `siyuan_insert_block`, `siyuan_append_block`, `siyuan_set_block_attrs`, `siyuan_daily_note`
- Sidecar Docker container running alongside SiYuan, reaching it at `http://siyuan:6806`
- Dual transport: streamable HTTP (for Claude Desktop / n8n) and stdio (for Claude Code)
- Deployment via Komodo (`km` CLI) — git-push triggers Docker build on Hetzner
- Private repo `CaseyRo/mcp-siyuan` on GitHub, published to PyPI as `mcp-siyuan`
- Future Tier 3 (PreCog freeze/thaw) and Tier 4 (housekeeping) are out of scope for this change

## Capabilities

### New Capabilities
- `siyuan-client`: HTTP client for SiYuan kernel API — auth, error handling, response parsing
- `read-query-tools`: Tier 1 MCP tools for reading notebooks, documents, blocks, and running SQL queries
- `write-tools`: Tier 2 MCP tools for creating/updating documents and blocks
- `server-transport`: FastMCP server setup with streamable HTTP and stdio transports
- `sidecar-deployment`: Dockerfile, docker-compose.sidecar.yml, and Komodo stack config for git-push deploy

### Modified Capabilities

## Impact

- **New repo**: `CaseyRo/mcp-siyuan` (private) — Python, uv/pyproject.toml
- **Dependencies**: FastMCP 3.x, httpx, pydantic
- **Infrastructure**: New sidecar container on Komodo/Hetzner alongside existing SiYuan stack
- **Clients**: Claude Desktop config, Claude Code MCP config, n8n MCP nodes
- **Related**: CDI-33 (RambleRouter) will consume this server; CDI-101 (PreCog) will add Tier 3 tools later
