## Why

SiYuan MCP has no way to reorganise documents or blocks programmatically. Moving or renaming documents requires recreating them in the new location and deleting the originals — losing block IDs, references, and history. Hit this during campaign 001 content restructuring (CDI-860) where 16 documents had to be recreated from scratch.

## What Changes

- Add `siyuan_move_doc` tool — move one or more documents to a new parent document or notebook, using ID-based API for LLM ergonomics.
- Add `siyuan_rename_doc` tool — rename a document by ID without moving it.
- Add `siyuan_move_block` tool — move a block to a different parent or after a sibling block.
- Register all three tools in the MCP server as Tier 2 (Write) tools.

## Capabilities

### New Capabilities
- `doc-move-rename`: Document move and rename operations via SiYuan filetree API.
- `block-move`: Block repositioning within and across documents via SiYuan block API.

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- `mcp_siyuan/tools/write.py` — three new async tool functions
- `mcp_siyuan/server.py` — register three new tools in Tier 2
- `tests/test_tools_write.py` — new test cases for each tool
- SiYuan API endpoints used: `/api/filetree/moveDocsByID`, `/api/filetree/renameDocByID`, `/api/block/moveBlock`
