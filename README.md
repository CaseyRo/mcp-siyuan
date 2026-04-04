# mcp-siyuan

MCP server for SiYuan Notes built on FastMCP 3.x.

## PDF Export

The `siyuan_export_pdf` tool converts SiYuan documents to PDF using WeasyPrint.

**Features:** Configurable page size (A3, A4, A5, Letter, Legal, Tabloid), orientation (portrait/landscape), and image quality (1-100).

**Known limitation:** Math blocks (KaTeX/MathJax) render as raw LaTeX — WeasyPrint does not execute JavaScript.

**Docker requirements:** The Dockerfile installs Pango, Cairo, and Noto fonts for WeasyPrint rendering. The container has a 512MB memory limit.
