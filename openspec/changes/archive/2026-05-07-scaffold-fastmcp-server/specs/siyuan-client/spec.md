## ADDED Requirements

### Requirement: HTTP client connects to SiYuan kernel
The system SHALL provide an async HTTP client that communicates with the SiYuan kernel API using httpx.AsyncClient with connection pooling. The client SHALL read `SIYUAN_URL` (default `http://siyuan:6806`) and `SIYUAN_TOKEN` from environment variables.

#### Scenario: Successful API call
- **WHEN** the client sends a POST request to a SiYuan endpoint with valid token
- **THEN** the client returns the parsed `data` field from the response JSON

#### Scenario: Missing or invalid token
- **WHEN** the SiYuan kernel returns code != 0 due to auth failure
- **THEN** the client raises a descriptive error including the endpoint and error message

#### Scenario: SiYuan unreachable
- **WHEN** the SiYuan kernel is not reachable at the configured URL
- **THEN** the client raises a connection error with the target URL for diagnostics

### Requirement: Response envelope parsing
The system SHALL parse all SiYuan API responses as `{ code: int, msg: str, data: any }` envelopes. If `code != 0`, the client SHALL raise an error with the `msg` content.

#### Scenario: Successful response parsing
- **WHEN** the kernel returns `{ "code": 0, "msg": "", "data": { ... } }`
- **THEN** the client returns only the `data` value

#### Scenario: Error response parsing
- **WHEN** the kernel returns `{ "code": -1, "msg": "block not found" }`
- **THEN** the client raises an error containing "block not found"

### Requirement: Configuration via pydantic-settings
The system SHALL use pydantic-settings to load configuration from environment variables: `SIYUAN_URL`, `SIYUAN_TOKEN`, `TRANSPORT` (default: `stdio`).

#### Scenario: Default configuration
- **WHEN** no environment variables are set except `SIYUAN_TOKEN`
- **THEN** `SIYUAN_URL` defaults to `http://siyuan:6806` and `TRANSPORT` defaults to `stdio`
