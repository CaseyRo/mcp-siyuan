## ADDED Requirements

### Requirement: FastMCP server initialization
The system SHALL create a FastMCP server instance with name `mcp-siyuan` that registers all Tier 1 and Tier 2 tools via `@mcp.tool` decorators.

#### Scenario: Server starts and lists tools
- **WHEN** the server starts and a client requests the tool list
- **THEN** all 12 tools (6 read + 6 write) are listed with descriptions and parameter schemas

### Requirement: Streamable HTTP transport
The system SHALL support running as an HTTP server via `mcp.run(transport="http", host="0.0.0.0", port=8000)` when `TRANSPORT=http` is set.

#### Scenario: HTTP transport startup
- **WHEN** `TRANSPORT=http` is set and the server starts
- **THEN** the server listens on `0.0.0.0:8000` and serves MCP over streamable HTTP

### Requirement: stdio transport
The system SHALL support running over stdio via `mcp.run()` (default) when `TRANSPORT=stdio` is set or no transport is specified.

#### Scenario: stdio transport startup
- **WHEN** `TRANSPORT=stdio` or no transport env var is set
- **THEN** the server communicates over stdin/stdout using MCP stdio protocol

### Requirement: Server entry point
The system SHALL provide a `__main__.py` or `server.py` entry point runnable via `python -m mcp_siyuan` or `mcp-siyuan` console script.

#### Scenario: Run via module
- **WHEN** `python -m mcp_siyuan` is executed
- **THEN** the server starts with the configured transport
