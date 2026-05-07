## 1. Tool Implementation

- [ ] 1.1 Add `siyuan_move_doc` function to `mcp_siyuan/tools/write.py`
- [ ] 1.2 Add `siyuan_rename_doc` function to `mcp_siyuan/tools/write.py`
- [ ] 1.3 Add `siyuan_move_block` function to `mcp_siyuan/tools/write.py` with validation

## 2. Server Registration

- [ ] 2.1 Import and register all three tools in `mcp_siyuan/server.py` under Tier 2

## 3. Tests

- [ ] 3.1 Add tests for `siyuan_move_doc` (single doc, multiple docs)
- [ ] 3.2 Add test for `siyuan_rename_doc`
- [ ] 3.3 Add tests for `siyuan_move_block` (previous_id, parent_id, both, neither)

## 4. Verify

- [ ] 4.1 Run full test suite and confirm all pass
