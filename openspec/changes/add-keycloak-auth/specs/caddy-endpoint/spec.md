## ADDED Requirements

### Requirement: Caddy reverse proxy for mcp-siyuan
The Caddy configuration SHALL include a site block for `mcp-siyuan.cdit-dev.de` that proxies to the mcp-siyuan container with SSE-compatible settings (flush_interval -1).

#### Scenario: MCP client connects via HTTPS
- **WHEN** a client connects to `https://mcp-siyuan.cdit-dev.de/mcp`
- **THEN** Caddy proxies the request to the mcp-siyuan backend with streaming enabled

### Requirement: Well-known endpoint rewrite
The Caddy config SHALL rewrite `/.well-known/oauth-protected-resource` to the FastMCP path pattern at `/mcp/.well-known/oauth-protected-resource`.

#### Scenario: OAuth discovery via well-known
- **WHEN** a client fetches `https://mcp-siyuan.cdit-dev.de/.well-known/oauth-protected-resource`
- **THEN** Caddy rewrites and proxies to the backend which returns Keycloak metadata
