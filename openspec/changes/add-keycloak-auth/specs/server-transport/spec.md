## MODIFIED Requirements

### Requirement: FastMCP server initialization
The system SHALL create a FastMCP server instance with name `mcp-siyuan` that registers all tools via `@mcp.tool` decorators. The server SHALL accept an `auth` parameter from the MultiAuth provider.

#### Scenario: Server starts with auth enabled
- **WHEN** the server starts with Keycloak and API key configured
- **THEN** all MCP endpoints require valid authentication

#### Scenario: Server lists tools after auth
- **WHEN** an authenticated client requests the tool list
- **THEN** all 19 tools are listed with descriptions and parameter schemas
