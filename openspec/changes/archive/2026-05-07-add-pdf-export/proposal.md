## Why

SiYuan Note does not offer a native PDF export API. Users who want to share or archive documents as PDFs must use the desktop app's manual export. By adding a `siyuan_export_pdf` tool to our MCP server, any LLM client can generate PDFs from SiYuan documents on demand — enabling automated report generation, archival workflows, and sharing with non-SiYuan users.

## What Changes

- Add a new `siyuan_export_pdf` MCP tool that accepts a document ID and rendering options (orientation, page size, image quality) and returns a base64-encoded PDF or a file path
- Leverage SiYuan's built-in `/api/export/exportPreviewHTML` endpoint to get fully-rendered, styled HTML (this endpoint is SiYuan's own PDF-preview renderer — it already handles all block types, CSS, math, code highlighting, and has an `image` flag for embedded images)
- Feed the SiYuan-rendered HTML into a PDF rendering library (e.g., weasyprint, playwright, or pdfkit) — no custom markdown-to-HTML pipeline needed
- Support both portrait and landscape orientation, with configurable page sizes — EU (A4, A3, A5) and US (Letter, Legal, Tabloid)
- Optimise embedded images for PDF file size (downscale, compress, respect a configurable quality setting)
- Add a new tools module `mcp_siyuan/tools/export.py` for export-related tools
- Add comprehensive tests covering block type rendering, orientation variants, long/short content, and image optimisation

## Capabilities

### New Capabilities
- `pdf-export`: PDF generation from SiYuan documents — SiYuan HTML export integration, PDF rendering, page layout options, image optimisation, and output format (base64/bytes)

### Modified Capabilities
_(none — this is a purely additive feature)_

## Impact

- **New dependency**: A PDF rendering library (e.g., `weasyprint`, `playwright`, or `pdfkit`/`wkhtmltopdf`). Choice affects Docker image size and system-level dependencies.
- **Docker**: The Dockerfile may need additional system packages for the chosen PDF renderer (fonts, headless browser binaries, etc.)
- **Server registration**: `server.py` gains a new tool import and registration (`siyuan_export_pdf`)
- **Client**: The existing `SiYuanClient` is used to call `/api/export/exportPreviewHTML` (with `id`, `keepFold`, `merge`, `image` params) instead of the markdown export endpoint
- **SiYuan API surface**: Uses `exportPreviewHTML` (primary) and possibly `exportHTML` (with `pdf=true` flag) — both are undocumented but stable internal endpoints
- **Tests**: New test module `tests/test_tools_export.py` with fixtures for diverse block types and PDF validation
- **File size**: PDF output with images can be large; the tool should support size-optimised output and warn or truncate for very large documents
