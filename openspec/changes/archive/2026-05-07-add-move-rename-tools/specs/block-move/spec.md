## ADDED Requirements

### Requirement: Move block to new position
The system SHALL provide a `siyuan_move_block` tool that moves a block to a new position relative to an anchor block.

The tool SHALL accept:
- `id` (str, required): Block ID to move.
- `parent_id` (str, optional, default ""): Target parent block ID — makes the block a child of this parent.
- `previous_id` (str, optional, default ""): Place the block after this sibling block.

At least one of `parent_id` or `previous_id` MUST be provided. If both are provided, `previous_id` takes precedence (matching SiYuan API behavior).

The tool SHALL call `/api/block/moveBlock` with `id`, `parentID`, and `previousID` parameters.
The tool SHALL return a dict via `_wrap_result()`.

#### Scenario: Move block after a sibling
- **WHEN** `siyuan_move_block(id="block1", previous_id="sibling1")` is called
- **THEN** the tool calls `/api/block/moveBlock` with `id="block1"`, `previousID="sibling1"`, `parentID=""`
- **THEN** returns the wrapped result

#### Scenario: Move block as child of parent
- **WHEN** `siyuan_move_block(id="block1", parent_id="parent1")` is called
- **THEN** the tool calls `/api/block/moveBlock` with `id="block1"`, `previousID=""`, `parentID="parent1"`
- **THEN** returns the wrapped result

#### Scenario: Both previous_id and parent_id provided
- **WHEN** `siyuan_move_block(id="block1", previous_id="sibling1", parent_id="parent1")` is called
- **THEN** the tool sends both `previousID="sibling1"` and `parentID="parent1"` to the API
- **THEN** SiYuan uses `previousID` for positioning (API precedence rule)

#### Scenario: Neither parent_id nor previous_id provided
- **WHEN** `siyuan_move_block(id="block1")` is called with no anchor
- **THEN** the tool raises a `ValueError`

### Requirement: Tool registered in MCP server
The system SHALL register `siyuan_move_block` in `server.py` under the Tier 2 (Write) section.

#### Scenario: Tool available via MCP
- **WHEN** the MCP server starts
- **THEN** `siyuan_move_block` is available as a callable tool
