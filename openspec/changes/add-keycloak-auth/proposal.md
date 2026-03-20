## Why

mcp-siyuan currently runs without authentication. Claude Desktop (claude.ai connector) requires OAuth 2.1 via Keycloak to connect. Direct clients (Claude Code, n8n) need bearer token auth. The existing CDIT pattern (mcp-things, mcp-watermelon) uses FastMCP's MultiAuth with Keycloak JWT + static API key. We need to replicate this, add a Caddy reverse proxy endpoint, and register a Keycloak client.

## What Changes

- Dual authentication: Keycloak JWT (for Claude.ai) + bearer token (for Claude Code/n8n) via FastMCP MultiAuth
- RFC 9728 Protected Resource Metadata at `/.well-known/oauth-protected-resource`
- Auto-generated API key on first startup (prefix `smcp_`)
- Caddy reverse proxy endpoint at `mcp-siyuan.cdit-dev.de`
- Keycloak client `mcp-siyuan` in `cdit-mcp` realm
- Config extended with `KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE`, `MCP_SIYUAN_API_KEY`, `MCP_SIYUAN_PUBLIC_URL`

## Capabilities

### New Capabilities
- `mcp-auth`: Dual authentication (Keycloak JWT + bearer token), API key generation, RFC 9728 metadata
- `caddy-endpoint`: Caddy reverse proxy config for mcp-siyuan.cdit-dev.de

### Modified Capabilities
- `server-transport`: Server now requires auth provider passed to FastMCP constructor
- `sidecar-deployment`: Container needs auth env vars, Caddy needs config update

## Impact

- **mcp_siyuan/auth.py**: New module — BearerTokenVerifier, create_auth, generate_api_key
- **mcp_siyuan/config.py**: Extended with auth settings
- **mcp_siyuan/server.py**: FastMCP init now passes `auth=` parameter
- **Caddy**: New site block in ~/dev/caddy/Caddyfile
- **Keycloak**: New client in cdit-mcp realm (manual step)
- **Running container**: Needs restart with new env vars
