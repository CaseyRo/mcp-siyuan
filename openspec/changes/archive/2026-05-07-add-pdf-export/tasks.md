## 1. Dependencies & Docker

- [x] 1.1 Add `weasyprint` to `pyproject.toml` dependencies
- [x] 1.2 Update `Dockerfile` to install WeasyPrint system dependencies (`libpango-1.0-0`, `libpangocairo-1.0-0`, `libgdk-pixbuf2.0-0`, `libffi8`, `libcairo2`, `fonts-noto-core`) — use `libffi8` not `libffi-dev` (runtime only, not dev headers)
- [x] 1.3 Verify Docker image builds and WeasyPrint imports successfully

## 2. SiYuan HTML Export Integration

- [x] 2.1 Add `_get_preview_html(id: str) -> tuple[str, str]` helper in `mcp_siyuan/tools/export.py` that calls `/api/export/exportPreviewHTML` via `sy.call` and returns `(name, html)`
- [x] 2.2 Investigate whether `exportPreviewHTML` with `image=true` embeds images as data URIs or uses relative URLs — adjust `base_url` strategy accordingly
- [x] 2.3 Test which SiYuan endpoint (`exportPreviewHTML` vs `exportHTML` with `pdf=true`) produces the cleanest static HTML for WeasyPrint

## 3. Security Hardening

- [x] 3.1 Implement `_restricted_fetcher(url)` — custom WeasyPrint URL fetcher that allows only `data:` URIs and fetches to the SiYuan origin (`settings.siyuan_url`), blocking all other hosts (SSRF prevention)
- [x] 3.2 Add `_validate_id(id: str)` helper with regex `^\d{14}-[a-z0-9]{7}$` matching SiYuan's block ID format — call before any API request
- [x] 3.3 Add `MAX_HTML_BYTES = 20 * 1024 * 1024` cap on HTML response size before passing to WeasyPrint (OOM prevention)
- [x] 3.4 Add `deploy.resources.limits.memory: 512m` to the mcp-siyuan service in `compose.yaml`
- [x] 3.5 Wrap all WeasyPrint calls in try/except — log full error server-side, return generic `SiYuanError("PDF rendering failed. Check server logs for details.")` to caller (prevent path/internal leakage)

## 4. PDF Rendering Core

- [x] 4.1 Create `mcp_siyuan/tools/export.py` module with `PAGE_SIZES` dict (A3, A4, A5, Letter, Legal, Tabloid in mm)
- [x] 4.2 Implement `_page_css(page_size: str, orientation: str) -> str` helper that generates the `@page` CSS rule with correct dimensions (swap width/height for landscape)
- [x] 4.3 Implement `_render_pdf(html: str, orientation: str, page_size: str, image_quality: int) -> bytes` using WeasyPrint's `HTML(string=..., base_url=...).write_pdf()` with `url_fetcher=_restricted_fetcher`, CSS stylesheet injection, `optimize_images=True`, and `jpeg_quality` param
- [x] 4.4 Implement the public `siyuan_export_pdf` tool function with Pydantic-validated params (`id`, `orientation`, `page_size`, `image_quality`), `_validate_id` check, HTML size cap, base64 encoding of output, SHA-256 hash, and large file warning (>10MB)

## 5. Server Registration

- [x] 5.1 Import `siyuan_export_pdf` in `server.py` and register with `mcp.tool()`
- [x] 5.2 Add math block limitation to the tool's docstring

## 6. Tests — Unit

- [x] 6.1 Create `tests/test_tools_export.py` with `mock_sy` fixture (same pattern as existing test files)
- [x] 6.2 Test `_get_preview_html` — correct API call to `exportPreviewHTML`, name extraction, error on missing doc
- [x] 6.3 Test `_page_css` — all 6 page sizes generate correct mm dimensions, landscape swaps width/height
- [x] 6.4 Test `siyuan_export_pdf` default call — returns dict with `name`, `pdf_base64`, `sha256` keys, PDF starts with `%PDF-` after decoding
- [x] 6.5 Test invalid `page_size` and out-of-range `image_quality` raise validation errors
- [x] 6.6 Test large file warning — mock a >10MB PDF response and verify `warning` field present
- [x] 6.7 Test `_validate_id` rejects malformed IDs (empty, path traversal, wrong format) and accepts valid SiYuan IDs
- [x] 6.8 Test `_restricted_fetcher` blocks non-SiYuan origins and allows `data:` URIs + SiYuan-origin URLs
- [x] 6.9 Test HTML size cap — mock an oversized HTML response and verify it raises before reaching WeasyPrint
- [x] 6.10 Test WeasyPrint error wrapping — trigger a rendering error and verify caller gets generic message, not internal paths

## 7. Tests — Rendering Quality

- [x] 7.1 Create HTML fixtures for diverse block types: headings, paragraphs, lists, blockquotes, code blocks, tables, images
- [x] 7.2 Test short content (few lines) produces a single-page PDF
- [x] 7.3 Test long content (many paragraphs) produces multi-page PDF
- [x] 7.4 Test portrait vs landscape produce PDFs with different page dimensions
- [x] 7.5 Test image quality parameter affects PDF file size (quality=40 < quality=100)
- [x] 7.6 Test each EU (A3, A4, A5) and US (Letter, Legal, Tabloid) page size renders without error

## 8. Documentation

- [x] 8.1 Document math block limitation (raw LaTeX output) in tool docstring
- [x] 8.2 Update README with PDF export feature and Docker requirements
