## Context

CDIT MCP servers use a proven dual-auth pattern: Keycloak OIDC for web clients (Claude.ai) and static bearer tokens for direct clients (Claude Code, n8n). This is implemented via FastMCP 3.x's `MultiAuth`, `JWTVerifier`, and `RemoteAuthProvider`. The pattern is live in mcp-things and mcp-watermelon.

Keycloak runs at `auth.cdit-works.de` with realm `cdit-mcp`. Caddy terminates TLS and proxies to backend services. The MCP server itself handles all auth — no proxy-level auth.

## Goals / Non-Goals

**Goals:**
- Add Keycloak JWT + bearer token auth matching mcp-things pattern exactly
- Serve RFC 9728 metadata so Claude.ai can discover the auth server
- Auto-generate API key on first run (prefix `smcp_`)
- Add Caddy endpoint at `mcp-siyuan.cdit-dev.de`
- Document Keycloak client setup steps

**Non-Goals:**
- Modifying Keycloak server config (manual step via admin UI)
- Role-based access control on individual tools
- Client compatibility middleware (not needed initially — can add later)

## Decisions

### D1: Reuse mcp-things auth pattern verbatim
**Choice:** Copy the `BearerTokenVerifier` + `JWTVerifier` + `RemoteAuthProvider` + `MultiAuth` pattern from mcp-things.
**Why:** Proven, already works with Claude.ai connector. FastMCP's auth API is the same across servers.

### D2: API key prefix `smcp_`
**Choice:** API keys prefixed `smcp_` (SiYuan MCP) to distinguish from `tmcp_` (Things MCP).
**Why:** Easy to identify which server a key belongs to when managing multiple MCP servers.

### D3: Caddy on same pattern as mcp-watermelon
**Choice:** SiYuan runs on `ubuntu-smurf-mirror` same as the watermelon MCP. Use `MCP_SIYUAN_HOST` env var in Caddyfile, same rewrite pattern for well-known endpoint.
**Why:** Consistent infrastructure. Caddy config is git-push deployed from ~/dev/caddy.

### D4: Config env var naming
**Choice:** `MCP_SIYUAN_API_KEY`, `MCP_SIYUAN_PUBLIC_URL` for server-specific auth settings. Shared `KEYCLOAK_ISSUER` and `KEYCLOAK_AUDIENCE` for Keycloak config.
**Why:** Follows mcp-things naming convention (`THINGS_MCP_API_KEY` → `MCP_SIYUAN_API_KEY`).

## Risks / Trade-offs

- **Keycloak downtime** → Bearer token auth still works as fallback for direct clients; only Claude.ai connector is affected
- **JWKS caching** → FastMCP's JWTVerifier caches JWKS keys; key rotation in Keycloak propagates within cache TTL
- **Port 8006 on host** → Currently bound to loopback only; Caddy connects via Tailscale/internal network to `ubuntu-smurf-mirror`
