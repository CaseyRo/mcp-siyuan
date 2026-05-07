## ADDED Requirements

### Requirement: Move documents by ID
The system SHALL provide a `siyuan_move_doc` tool that moves one or more documents to a target parent document or notebook using document IDs.

The tool SHALL accept:
- `from_ids` (list of str, required): Document IDs to move.
- `to_id` (str, required): Target parent document ID or notebook ID.

The tool SHALL call `/api/filetree/moveDocsByID` with `fromIDs` and `toID` parameters.
The tool SHALL return a dict via `_wrap_result()`.

#### Scenario: Move single document to notebook root
- **WHEN** `siyuan_move_doc(from_ids=["doc1"], to_id="notebook1")` is called
- **THEN** the tool calls `/api/filetree/moveDocsByID` with `fromIDs=["doc1"]` and `toID="notebook1"`
- **THEN** returns `{"ok": True}`

#### Scenario: Move multiple documents to a parent document
- **WHEN** `siyuan_move_doc(from_ids=["doc1", "doc2"], to_id="parent-doc")` is called
- **THEN** the tool calls `/api/filetree/moveDocsByID` with `fromIDs=["doc1", "doc2"]` and `toID="parent-doc"`
- **THEN** returns `{"ok": True}`

### Requirement: Rename document by ID
The system SHALL provide a `siyuan_rename_doc` tool that renames a document's title without moving it.

The tool SHALL accept:
- `id` (str, required): Document ID to rename.
- `title` (str, required): New document title.

The tool SHALL call `/api/filetree/renameDocByID` with `id` and `title` parameters.
The tool SHALL return a dict via `_wrap_result()`.

#### Scenario: Rename a document
- **WHEN** `siyuan_rename_doc(id="doc1", title="New Title")` is called
- **THEN** the tool calls `/api/filetree/renameDocByID` with `id="doc1"` and `title="New Title"`
- **THEN** returns `{"ok": True}`

### Requirement: Tools registered in MCP server
The system SHALL register `siyuan_move_doc` and `siyuan_rename_doc` in `server.py` under the Tier 2 (Write) section.

#### Scenario: Tools available via MCP
- **WHEN** the MCP server starts
- **THEN** `siyuan_move_doc` and `siyuan_rename_doc` are available as callable tools
