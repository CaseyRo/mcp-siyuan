## ADDED Requirements

### Requirement: siyuan_create_document tool
The system SHALL expose an MCP tool `siyuan_create_document` that creates a new document by calling `POST /api/filetree/createDocWithMd`. The tool SHALL accept `notebook` (string), `path` (string), and `markdown` (string, optional) parameters. It SHALL return the new document's id.

#### Scenario: Create empty document
- **WHEN** the tool is called with notebook id and path, no markdown
- **THEN** it creates the document and returns its id

#### Scenario: Create document with content
- **WHEN** the tool is called with notebook id, path, and markdown content
- **THEN** it creates the document with the given content and returns its id

### Requirement: siyuan_update_block tool
The system SHALL expose an MCP tool `siyuan_update_block` that updates an existing block's content by calling `POST /api/block/updateBlock`. The tool SHALL accept `id` (string), `data` (string), and `data_type` (string, default: `markdown`) parameters.

#### Scenario: Update block with markdown
- **WHEN** the tool is called with a valid block id and new markdown content
- **THEN** the block content is replaced and the operation details are returned

### Requirement: siyuan_insert_block tool
The system SHALL expose an MCP tool `siyuan_insert_block` that inserts a new block by calling `POST /api/block/insertBlock`. The tool SHALL accept `data` (string), `data_type` (string, default: `markdown`), and one of `previous_id`, `next_id`, or `parent_id` to specify position.

#### Scenario: Insert block after existing block
- **WHEN** the tool is called with `previous_id` set to an existing block id
- **THEN** a new block is inserted after that block and its id is returned

#### Scenario: Insert block as child of parent
- **WHEN** the tool is called with `parent_id` set to a document or container block id
- **THEN** a new block is inserted as a child and its id is returned

### Requirement: siyuan_append_block tool
The system SHALL expose an MCP tool `siyuan_append_block` that appends content to the end of a document or container block by calling `POST /api/block/appendBlock`. The tool SHALL accept `data` (string), `data_type` (string, default: `markdown`), and `parent_id` (string).

#### Scenario: Append paragraph to document
- **WHEN** the tool is called with a document id as parent_id and markdown content
- **THEN** the content is appended at the end of the document

### Requirement: siyuan_set_block_attrs tool
The system SHALL expose an MCP tool `siyuan_set_block_attrs` that sets attributes on a block by calling `POST /api/attr/setBlockAttrs`. The tool SHALL accept `id` (string) and `attrs` (dict of string keys/values).

#### Scenario: Set custom attributes
- **WHEN** the tool is called with `attrs={"custom-status": "reviewed", "custom-priority": "high"}`
- **THEN** those attributes are set on the block

### Requirement: siyuan_daily_note tool
The system SHALL expose an MCP tool `siyuan_daily_note` that creates or opens today's daily note by calling `POST /api/filetree/createDailyNote`. The tool SHALL accept a `notebook` (string) parameter and return the daily note document id.

#### Scenario: Create today's daily note
- **WHEN** the tool is called with a notebook id and no daily note exists for today
- **THEN** it creates the daily note and returns its id

#### Scenario: Open existing daily note
- **WHEN** the tool is called and today's daily note already exists
- **THEN** it returns the existing daily note's id
