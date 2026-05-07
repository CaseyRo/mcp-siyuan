## ADDED Requirements

### Requirement: Per-Request Correlation ID

Every MCP tool invocation handled by `mcp-siyuan` SHALL be assigned a unique correlation ID (UUIDv4) at request entry. The correlation ID MUST be stored in an async-safe context such that any code executed during the call can retrieve the current request's ID. The correlation ID MUST be included in every log record emitted during the call and MUST be returned to the caller as part of any error response surfaced by this server.

#### Scenario: Tool call assigned a fresh correlation ID

- **WHEN** any registered MCP tool function is invoked
- **THEN** a UUIDv4 string is generated before the tool body runs
- **AND** the ID is stored in a `contextvars.ContextVar` for the duration of the call
- **AND** the ID appears in the entry log line for that call

#### Scenario: Correlation ID surfaced in error response

- **WHEN** a tool invocation raises an error that the server returns to the MCP client
- **THEN** the error payload includes the request's correlation ID under a `request_id` field

#### Scenario: Each invocation gets a distinct ID

- **WHEN** two tool calls execute concurrently in the same process
- **THEN** each call sees its own correlation ID via the context variable
- **AND** neither call's logs reference the other's ID

### Requirement: Structured Per-Request Logging

The server SHALL emit at least one structured log record per tool invocation in JSON format. Each record MUST include the fields `ts` (ISO-8601 UTC timestamp), `level`, `request_id`, `tool_name`, `caller`, `args_size_bytes`, `kernel_status`, `latency_ms`, `outcome`, and `message`. The `outcome` field MUST be one of `success`, `error`, or `validation_error`. The `caller` field MUST be populated from the Cloudflare Access JWT subject claim when present and `null` otherwise. The log level for the entire process MUST be configurable via the `SIYUAN_LOG_LEVEL` environment variable.

#### Scenario: Successful tool call logged with full fields

- **WHEN** a tool invocation completes without error
- **THEN** an exit log record is emitted with `outcome=success`
- **AND** the record contains all required fields with non-null values for `request_id`, `tool_name`, `args_size_bytes`, `kernel_status`, `latency_ms`, `outcome`

#### Scenario: Failed kernel call logged with error outcome

- **WHEN** a tool invocation reaches the SiYuan kernel and the kernel returns a non-success status
- **THEN** an exit log record is emitted with `outcome=error`
- **AND** `kernel_status` records the kernel's status code

#### Scenario: Validation error logged before kernel call

- **WHEN** a tool invocation fails Pydantic argument validation before any kernel call
- **THEN** an exit log record is emitted with `outcome=validation_error`
- **AND** `kernel_status` is `null`

#### Scenario: Caller extracted from Cloudflare Access JWT

- **WHEN** a tool invocation arrives with a valid CF Access JWT
- **THEN** the JWT's subject claim populates the `caller` field of the log record

#### Scenario: Log level honors environment variable

- **WHEN** the server starts with `SIYUAN_LOG_LEVEL=DEBUG`
- **THEN** debug-level log records are emitted
- **AND** when `SIYUAN_LOG_LEVEL` is unset, the default level is `INFO`

### Requirement: Diagnostic Endpoint for Recent Requests

The existing `/health` endpoint SHALL accept a `diag=1` query parameter. When set, the endpoint MUST return a JSON document containing the most recent request log records held in an in-memory ring buffer. The buffer size MUST be configurable via the `SIYUAN_DIAG_BUFFER_SIZE` environment variable with a default of 50. The endpoint MUST remain behind the same authentication used by the unparameterized `/health` endpoint. Without the query parameter, the endpoint's behavior MUST be unchanged from its prior contract.

#### Scenario: Plain health check unchanged

- **WHEN** a client calls `GET /health`
- **THEN** the response shape and status are unchanged from the prior implementation

#### Scenario: Diagnostic mode returns recent requests

- **WHEN** a client calls `GET /health?diag=1`
- **THEN** the response is a JSON object containing an array of the last N request log records
- **AND** N defaults to 50 when `SIYUAN_DIAG_BUFFER_SIZE` is unset

#### Scenario: Buffer is bounded

- **WHEN** more than `SIYUAN_DIAG_BUFFER_SIZE` requests have been processed
- **THEN** the ring buffer retains only the most recent `SIYUAN_DIAG_BUFFER_SIZE` records

#### Scenario: Diagnostic mode respects auth

- **WHEN** an unauthenticated request hits `GET /health?diag=1`
- **THEN** the response is rejected by the same auth layer that gates `GET /health`

### Requirement: FastMCP Version Pinning and Startup Assertion

The `pyproject.toml` SHALL pin `fastmcp` to an exact version (no range). On server startup, the process MUST log the imported FastMCP version. If the imported version does not match the pin, the server MUST emit a high-severity log record but MUST NOT crash, so that operators can roll forward.

#### Scenario: Version logged at startup

- **WHEN** the server starts
- **THEN** an INFO log record is emitted containing `fastmcp_version` and the imported version string

#### Scenario: Version mismatch is loud but non-fatal

- **WHEN** the imported FastMCP version does not equal the pinned version
- **THEN** the server emits an `ERROR`-level log record naming both versions
- **AND** the server still starts and accepts requests

#### Scenario: Pyproject pins exactly

- **WHEN** `pyproject.toml` is parsed
- **THEN** the FastMCP dependency specifier is an exact equality pin (`==X.Y.Z`)
