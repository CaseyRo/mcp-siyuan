## 1. Project Scaffold

- [x] 1.1 Initialize git repo, create `pyproject.toml` with uv, FastMCP 3.x, httpx, pydantic, pydantic-settings dependencies
- [x] 1.2 Create package structure: `mcp_siyuan/` with `__init__.py`, `server.py`, `client.py`, `config.py`, `models.py`, `tools/__init__.py`, `tools/read.py`, `tools/write.py`
- [x] 1.3 Implement `config.py` with pydantic-settings: `SIYUAN_URL`, `SIYUAN_TOKEN`, `TRANSPORT`

## 2. SiYuan Client

- [x] 2.1 Implement `client.py` — async httpx client with connection pooling, auth header, response envelope parsing
- [x] 2.2 Implement `models.py` — Pydantic models for Notebook, Block, BlockAttrs, and SiYuan API response envelope

## 3. Tier 1 Read/Query Tools

- [x] 3.1 Implement `siyuan_list_notebooks` in `tools/read.py` — calls `/api/notebook/lsNotebooks`
- [x] 3.2 Implement `siyuan_sql_query` — calls `/api/query/sql` with `stmt` parameter
- [x] 3.3 Implement `siyuan_get_document` — calls `/api/export/exportMdContent` with `id` and `max_length` truncation
- [x] 3.4 Implement `siyuan_search` — calls `/api/search/fullTextSearchBlock` with `query` and `limit`
- [x] 3.5 Implement `siyuan_get_block` — calls `/api/block/getBlockInfo` with block `id`
- [x] 3.6 Implement `siyuan_get_block_attrs` — calls `/api/attr/getBlockAttrs` with block `id`

## 4. Tier 2 Write Tools

- [x] 4.1 Implement `siyuan_create_document` in `tools/write.py` — calls `/api/filetree/createDocWithMd`
- [x] 4.2 Implement `siyuan_update_block` — calls `/api/block/updateBlock` with `id`, `data`, `data_type`
- [x] 4.3 Implement `siyuan_insert_block` — calls `/api/block/insertBlock` with positional params
- [x] 4.4 Implement `siyuan_append_block` — calls `/api/block/appendBlock` with `parent_id` and `data`
- [x] 4.5 Implement `siyuan_set_block_attrs` — calls `/api/attr/setBlockAttrs` with `id` and `attrs`
- [x] 4.6 Implement `siyuan_daily_note` — calls `/api/filetree/createDailyNote` with `notebook`

## 5. Server Entry Point

- [x] 5.1 Implement `server.py` — FastMCP instance, register all tools, transport selection from config
- [x] 5.2 Add `__main__.py` for `python -m mcp_siyuan` entry point
- [x] 5.3 Add console script entry point in `pyproject.toml`

## 6. Sidecar Deployment

- [x] 6.1 Create `Dockerfile` — Python slim base, uv install, TRANSPORT=http default, expose 8000
- [x] 6.2 Create `docker-compose.sidecar.yml` — mcp-siyuan + SiYuan on shared network
- [x] 6.3 Add `.env.example` with documented environment variables
- [x] 6.4 Verify Komodo-compatible structure (Dockerfile at repo root, compose file)
