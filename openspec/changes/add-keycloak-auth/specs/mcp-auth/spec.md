## ADDED Requirements

### Requirement: Dual authentication via MultiAuth
The system SHALL support simultaneous Keycloak JWT and bearer token authentication using FastMCP's MultiAuth provider. JWT validation SHALL use the Keycloak JWKS endpoint. Bearer token validation SHALL use constant-time comparison.

#### Scenario: Valid Keycloak JWT
- **WHEN** a request includes a valid JWT issued by the configured Keycloak realm
- **THEN** the request is authenticated and tool execution proceeds

#### Scenario: Valid bearer token
- **WHEN** a request includes `Authorization: Bearer <API_KEY>` matching the configured key
- **THEN** the request is authenticated and tool execution proceeds

#### Scenario: Invalid token
- **WHEN** a request includes an invalid or expired token
- **THEN** the request is rejected with a 401 response

### Requirement: RFC 9728 Protected Resource Metadata
The system SHALL serve OAuth Protected Resource Metadata at `/.well-known/oauth-protected-resource` via FastMCP's RemoteAuthProvider, pointing clients to the Keycloak authorization server.

#### Scenario: Metadata discovery
- **WHEN** a client fetches `/.well-known/oauth-protected-resource`
- **THEN** the response includes the Keycloak issuer URL as authorization server

### Requirement: Auto-generated API key
The system SHALL generate a cryptographically secure API key with prefix `smcp_` on first startup if `MCP_SIYUAN_API_KEY` is not set. The key SHALL be logged once at startup for the operator to capture.

#### Scenario: No API key configured
- **WHEN** `MCP_SIYUAN_API_KEY` is empty at startup
- **THEN** the server generates a key, logs it, and uses it for bearer token auth

#### Scenario: API key pre-configured
- **WHEN** `MCP_SIYUAN_API_KEY` is set in environment
- **THEN** the server uses that key without generating a new one
