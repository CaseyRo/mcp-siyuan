## ADDED Requirements

### Requirement: Optional Idempotency Key on Write Tools

Each of the five SiYuan write tools — `siyuan_create_document`, `siyuan_append_block`, `siyuan_insert_block`, `siyuan_update_block`, and `siyuan_set_block_attrs` — SHALL accept an optional `idempotency_key` argument of type `str | None`. When omitted or `null`, the tool MUST behave exactly as it did prior to this change. When provided, the server MUST consult an in-process replay cache before invoking the SiYuan kernel, and on a cache hit MUST return the cached prior result without making a new kernel call.

#### Scenario: Omitted key preserves legacy behavior

- **WHEN** a write tool is invoked without an `idempotency_key`
- **THEN** the tool calls the SiYuan kernel as before
- **AND** no replay-cache entry is created or consulted

#### Scenario: First call with key invokes kernel

- **WHEN** a write tool is invoked with `idempotency_key="K1"` and no prior cache entry exists for `(tool_name, "K1")`
- **THEN** the tool calls the SiYuan kernel
- **AND** on success, the kernel response is written to the cache under `(tool_name, "K1")`

#### Scenario: Replay within TTL returns cached result

- **WHEN** a write tool is invoked with `idempotency_key="K1"`
- **AND** a cache entry exists for `(tool_name, "K1")`
- **AND** the entry is younger than `SIYUAN_IDEMPOTENCY_TTL_SECONDS`
- **THEN** the tool returns the cached result
- **AND** no kernel call is made

#### Scenario: Replay after TTL invokes kernel again

- **WHEN** a write tool is invoked with `idempotency_key="K1"`
- **AND** the prior cache entry for `(tool_name, "K1")` is older than `SIYUAN_IDEMPOTENCY_TTL_SECONDS`
- **THEN** the tool calls the SiYuan kernel
- **AND** the new result replaces the expired cache entry

#### Scenario: All five write tools support the key

- **WHEN** any of `siyuan_create_document`, `siyuan_append_block`, `siyuan_insert_block`, `siyuan_update_block`, or `siyuan_set_block_attrs` is inspected
- **THEN** its argument schema includes an optional `idempotency_key` field

### Requirement: Idempotency Key Validation

If an `idempotency_key` is supplied, it MUST be a non-empty string of at most 128 characters matching the regex `^[A-Za-z0-9_\-:.]+$`. Invalid keys MUST cause the tool to return a validation error before any kernel call is made and before the cache is consulted.

#### Scenario: Empty key rejected

- **WHEN** a write tool is invoked with `idempotency_key=""`
- **THEN** the tool returns a validation error
- **AND** no kernel call is made

#### Scenario: Over-length key rejected

- **WHEN** a write tool is invoked with an `idempotency_key` longer than 128 characters
- **THEN** the tool returns a validation error

#### Scenario: Disallowed character rejected

- **WHEN** a write tool is invoked with `idempotency_key="bad key!"`
- **THEN** the tool returns a validation error

#### Scenario: Valid key accepted

- **WHEN** a write tool is invoked with `idempotency_key="funkstrecke-2026-04-29:v1"`
- **THEN** the tool proceeds to the cache lookup

### Requirement: Failures Are Not Cached

Only successful kernel responses SHALL be stored in the idempotency cache. If the kernel returns a non-success status, raises an exception, or the call times out, the server MUST NOT write a cache entry for that `(tool_name, idempotency_key)` pair, so that a client retry can produce a fresh kernel call.

#### Scenario: Kernel error does not poison cache

- **WHEN** a write tool with `idempotency_key="K2"` invokes the kernel and the kernel returns an error
- **THEN** no cache entry is created for `(tool_name, "K2")`
- **AND** a subsequent call with the same key invokes the kernel again

#### Scenario: Exception does not poison cache

- **WHEN** a write tool with `idempotency_key="K3"` raises an unexpected exception during the kernel call
- **THEN** no cache entry is created for `(tool_name, "K3")`

### Requirement: Bounded In-Process Cache

The replay cache SHALL be a single in-process bounded cache shared across all write tools, keyed by `(tool_name, idempotency_key)`. The cache MUST have a maximum size of 1024 entries with TTL eviction. The TTL MUST be configurable via the `SIYUAN_IDEMPOTENCY_TTL_SECONDS` environment variable with a default of 300 seconds.

#### Scenario: Cache key namespaced by tool name

- **WHEN** `siyuan_create_document` is invoked with `idempotency_key="K4"`
- **AND** subsequently `siyuan_append_block` is invoked with `idempotency_key="K4"`
- **THEN** the second call does not return the first call's cached result
- **AND** both calls invoke the kernel independently

#### Scenario: Default TTL applied

- **WHEN** the server starts with `SIYUAN_IDEMPOTENCY_TTL_SECONDS` unset
- **THEN** the cache TTL is 300 seconds

#### Scenario: Cache is per-process

- **WHEN** `mcp-siyuan` is deployed as a single replica
- **THEN** the cache is local to that process and not shared across replicas
- **AND** the README documents this single-replica constraint
