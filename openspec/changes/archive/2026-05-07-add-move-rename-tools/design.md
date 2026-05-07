## Context

mcp-siyuan exposes SiYuan's kernel API as MCP tools. Write tools live in `mcp_siyuan/tools/write.py`, follow a consistent pattern (async, `sy.call()`, `_wrap_result()`), and are registered in `server.py`. SiYuan offers both path-based and ID-based variants for filetree operations; LLM agents work with block/doc IDs, not file paths.

## Goals / Non-Goals

**Goals:**
- Add three write tools: `siyuan_move_doc`, `siyuan_rename_doc`, `siyuan_move_block`
- Use ID-based SiYuan API endpoints for LLM ergonomics
- Follow existing write.py conventions exactly
- Full test coverage matching test_tools_write.py patterns

**Non-Goals:**
- Path-based move/rename variants (agents don't have file paths)
- Batch rename operations
- Undo/rollback support (SiYuan handles this in-app)

## Decisions

**1. Use ID-based API endpoints over path-based**
- `moveDocsByID` instead of `moveDocs` — agents have doc IDs from search/query, not `.sy` file paths
- `renameDocByID` instead of `renameDoc` — same reasoning, avoids needing notebook+path pair
- Alternative: path-based APIs would require agents to first resolve IDs to paths, adding a round-trip

**2. `siyuan_move_doc` accepts a list of IDs**
- Mirrors `moveDocsByID` which takes `fromIDs[]` — supports bulk moves in one call
- More efficient for restructuring operations (the original pain point)

**3. `siyuan_move_block` uses position + anchor_id pattern**
- Consistent with `siyuan_insert_block`'s interface
- Maps to `moveBlock`'s `previousID`/`parentID` parameters
- Default position is "after" (move after a sibling), with "child" for reparenting

## Risks / Trade-offs

- [Null data responses] → All three endpoints return `data: null` on success. `_wrap_result()` handles this correctly, returning `{"ok": True}`.
- [moveDocsByID target is ambiguous] → `toID` can be a notebook ID or document ID. Docstring must clarify this to avoid agent confusion.
