## ADDED Requirements

### Requirement: siyuan_list_notebooks tool
The system SHALL expose an MCP tool `siyuan_list_notebooks` that returns all notebooks in the workspace by calling `POST /api/notebook/lsNotebooks`. The tool SHALL return a list of notebooks with id, name, icon, sort, and closed status.

#### Scenario: List all notebooks
- **WHEN** the tool is called with no parameters
- **THEN** it returns a list of notebook objects with fields: id, name, icon, sort, closed

### Requirement: siyuan_sql_query tool
The system SHALL expose an MCP tool `siyuan_sql_query` that executes a SQL statement against SiYuan's internal SQLite database by calling `POST /api/query/sql`. The tool SHALL accept a `stmt` parameter (string).

#### Scenario: Query blocks by content
- **WHEN** the tool is called with `stmt="SELECT id, content FROM blocks WHERE content LIKE '%TODO%' LIMIT 5"`
- **THEN** it returns the matching rows as a list of dicts

#### Scenario: Invalid SQL
- **WHEN** the tool is called with an invalid SQL statement
- **THEN** it returns the error message from SiYuan's response

### Requirement: siyuan_get_document tool
The system SHALL expose an MCP tool `siyuan_get_document` that retrieves a document's markdown content by calling `POST /api/export/exportMdContent` with the document `id`. The tool SHALL accept an `id` parameter and an optional `max_length` parameter (default: 65536) to truncate output.

#### Scenario: Retrieve full document
- **WHEN** the tool is called with a valid document id
- **THEN** it returns the markdown content of the document

#### Scenario: Truncated document
- **WHEN** the tool is called with `max_length=1000` and the document exceeds 1000 characters
- **THEN** it returns the first 1000 characters with a truncation notice appended

### Requirement: siyuan_search tool
The system SHALL expose an MCP tool `siyuan_search` that performs fulltext search by calling `POST /api/search/fullTextSearchBlock`. The tool SHALL accept a `query` parameter (string) and an optional `limit` parameter (default: 20).

#### Scenario: Search with results
- **WHEN** the tool is called with `query="meeting notes"`
- **THEN** it returns matching blocks with id, content, and parent document info

#### Scenario: Search with no results
- **WHEN** the tool is called with a query that matches nothing
- **THEN** it returns an empty list

### Requirement: siyuan_get_block tool
The system SHALL expose an MCP tool `siyuan_get_block` that retrieves a single block's content and metadata by calling `POST /api/block/getBlockInfo` with the block `id`.

#### Scenario: Get existing block
- **WHEN** the tool is called with a valid block id
- **THEN** it returns the block's content, type, and parent info

#### Scenario: Block not found
- **WHEN** the tool is called with a non-existent block id
- **THEN** it returns an error message indicating the block was not found

### Requirement: siyuan_get_block_attrs tool
The system SHALL expose an MCP tool `siyuan_get_block_attrs` that retrieves all attributes (system and custom) for a block by calling `POST /api/attr/getBlockAttrs` with the block `id`.

#### Scenario: Get block attributes
- **WHEN** the tool is called with a valid block id
- **THEN** it returns a dict of all attributes including id, type, updated, and any custom-* attributes
