## 1. Auth Module

- [x] 1.1 Create `mcp_siyuan/auth.py` — BearerTokenVerifier, create_auth(), generate_api_key() following mcp-things pattern
- [x] 1.2 Extend `mcp_siyuan/config.py` — add MCP_SIYUAN_API_KEY, MCP_SIYUAN_PUBLIC_URL, KEYCLOAK_ISSUER, KEYCLOAK_AUDIENCE settings

## 2. Server Integration

- [x] 2.1 Update `mcp_siyuan/server.py` — create auth provider and pass to FastMCP constructor
- [x] 2.2 Add API key auto-generation logic at startup (generate + log if not set)

## 3. Caddy Endpoint

- [x] 3.1 Add `mcp-siyuan.cdit-dev.de` site block to ~/dev/caddy/Caddyfile with well-known rewrite and reverse proxy
- [x] 3.2 Add `MCP_SIYUAN_HOST` env var to Caddy's .env

## 4. Deployment Config

- [x] 4.1 Update `.env.example` with auth environment variables
- [x] 4.2 Update compose.yaml with auth env vars

## 5. Tests

- [x] 5.1 Add tests for BearerTokenVerifier (valid key, invalid key, timing-safe)
- [x] 5.2 Add tests for create_auth() assembly
- [x] 5.3 Add tests for generate_api_key() format
- [x] 5.4 Update config tests for new auth settings

## 6. Deploy

- [ ] 6.1 Rebuild and restart mcp-siyuan container with auth env vars
- [ ] 6.2 Push Caddy config and deploy
- [ ] 6.3 Register `mcp-siyuan` client in Keycloak cdit-mcp realm (manual)
