## MODIFIED Requirements

### Requirement: Environment variable configuration
The sidecar SHALL read additional auth configuration from environment variables: `MCP_SIYUAN_API_KEY`, `MCP_SIYUAN_PUBLIC_URL`, `KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE`. The compose file and .env.example SHALL document these.

#### Scenario: Full auth configuration
- **WHEN** all auth env vars are set
- **THEN** the server starts with dual authentication (JWT + bearer token)

#### Scenario: Minimal configuration
- **WHEN** only `SIYUAN_TOKEN` and `KEYCLOAK_ISSUER` are set
- **THEN** the server auto-generates an API key and starts with both auth methods
