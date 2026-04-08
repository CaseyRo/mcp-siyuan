## Context

The MCP server is a Python FastMCP app (`python:3.12-slim` Docker image) that proxies SiYuan's kernel API as MCP tools. Tools are organised in `mcp_siyuan/tools/` modules (read, write, smart). The server runs alongside SiYuan on the same Docker network (`siyuan_default`), meaning it has direct HTTP access to SiYuan's API.

SiYuan provides `/api/export/exportPreviewHTML` — its own PDF-preview HTML renderer. This endpoint accepts `id`, `keepFold`, `merge`, and `image` parameters and returns fully-styled HTML with all block types rendered (headings, code with highlighting, tables, images). This eliminates the need for a custom markdown-to-HTML pipeline.

The remaining problem is HTML → PDF conversion in a headless server environment.

## Goals / Non-Goals

**Goals:**
- Expose a `siyuan_export_pdf` tool that converts any SiYuan document to PDF
- Support EU (A3, A4, A5) and US (Letter, Legal, Tabloid) page sizes, portrait and landscape
- Provide image quality control to manage output file size
- Minimise Docker image size increase
- Comprehensive test coverage for diverse block types and configurations

**Non-Goals:**
- Custom CSS theming or branding on top of SiYuan's HTML output
- Batch/bulk export of multiple documents in one call
- Password-protected or encrypted PDFs
- Table of contents / bookmarks in the PDF (may revisit later)
- Serving the PDF as a downloadable file via HTTP — the MCP tool returns base64
- JavaScript-dependent rendering (e.g. KaTeX/MathJax math blocks) — documented as a known limitation

## Decisions

### 1. PDF renderer: WeasyPrint over Playwright

**Choice**: WeasyPrint

**Alternatives considered:**
- **Playwright (Chromium headless)**: Full browser engine with perfect CSS/JS support. But adds ~300-400MB to the Docker image and requires a long-running Chromium process (~80-150MB RAM). Overkill when SiYuan's HTML output is mostly standard CSS.
- **pdfkit / wkhtmltopdf**: Depends on a deprecated Qt WebKit engine. Poor modern CSS support.
- **Puppeteer**: Node.js-based — would add a Node runtime dependency to a Python project.

**Rationale**: WeasyPrint is a pure Python HTML/CSS-to-PDF renderer that adds ~50-80MB to the Docker image (Pango + system fonts). It supports CSS Flexbox, Grid, multi-column layouts, `@page` rules with custom sizes, and has **built-in image optimisation** (`--optimize-images`, `--jpeg-quality`, `--dpi`). This eliminates the need for Pillow as a separate dependency. The trade-off is no JavaScript execution, so math blocks (KaTeX/MathJax) will render as raw LaTeX — this is an acceptable limitation documented in the tool description.

### 2. Image optimisation approach

**Choice**: Use WeasyPrint's built-in image optimisation.

WeasyPrint supports `optimize_images=True` and `jpeg_quality` / `dpi` parameters directly in its `write_pdf()` API. No additional dependencies needed.

**Alternatives considered:**
- **Pillow pre-processing**: Decode images from HTML, re-encode at target quality. Adds a dependency and complexity for something WeasyPrint handles natively.
- **Post-PDF compression via Ghostscript**: Another system dependency with less control.

**Rationale**: WeasyPrint's built-in support is simpler, requires no extra dependencies, and gives us the quality/DPI controls we need.

### 3. Page size via CSS @page injection

**Choice**: Inject a `@page` CSS rule into the HTML before passing to WeasyPrint.

```python
css = f"@page {{ size: {width}mm {height}mm; margin: 15mm; }}"
HTML(string=html, base_url=siyuan_base).write_pdf(
    stylesheets=[CSS(string=css)],
    optimize_images=True,
    jpeg_quality=image_quality,
)
```

**Rationale**: WeasyPrint's `@page` size directive is the standard way to control page dimensions. We inject it as a user stylesheet so it overrides any existing page styles from SiYuan's HTML without modifying the HTML content itself.

### 4. Module structure

New file: `mcp_siyuan/tools/export.py`

```python
async def siyuan_export_pdf(
    id: str,
    orientation: Literal["portrait", "landscape"] = "portrait",
    page_size: Literal["A3", "A4", "A5", "Letter", "Legal", "Tabloid"] = "A4",
    image_quality: Annotated[int, Field(ge=1, le=100)] = 85,
) -> dict[str, str]:
```

Internal helpers (private, not exposed as tools):
- `_get_preview_html(id: str) -> tuple[str, str]` — calls `exportPreviewHTML`, returns `(name, html)`
- `_render_pdf(html: str, orientation: str, page_size: str, image_quality: int) -> bytes` — WeasyPrint HTML → PDF with page size CSS injection and image optimisation
- `_page_css(page_size: str, orientation: str) -> str` — generates the `@page` CSS rule

### 5. Page size mapping

```python
PAGE_SIZES: dict[str, tuple[float, float]] = {
    "A3": (297, 420),       # mm
    "A4": (210, 297),
    "A5": (148, 210),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
    "Tabloid": (279.4, 431.8),
}
```

For landscape, swap width and height before generating the `@page` CSS.

### 6. Base URL for asset resolution

WeasyPrint needs a `base_url` to resolve relative image/asset paths in SiYuan's HTML. We pass `settings.siyuan_url` so that relative paths like `/assets/image.png` resolve against the SiYuan instance.

### 7. Dockerfile changes

WeasyPrint requires Pango and its dependencies on `python:3.12-slim`:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*
```

`fonts-noto-core` provides good Unicode coverage for international content. Total addition: ~50-80MB.

### 8. Test strategy

Tests mock at one boundary:
- **SiYuan API**: Mock `sy.call` (existing pattern) to return sample HTML for different block type combinations

For WeasyPrint, we can do **real rendering** in tests (unlike Playwright which needs a browser binary). WeasyPrint runs as a pure library, so tests can:
- Assert the generated PDF is valid (check PDF header bytes `%PDF-`)
- Assert page count for short vs long documents
- Assert correct `@page` CSS is injected for each size/orientation combo
- Test image optimisation by comparing PDF sizes at different quality levels
- Test error handling (invalid doc ID, connection errors, invalid params)

This is a significant testing advantage over Playwright — no mocking of the renderer needed.

## Risks / Trade-offs

**[Math blocks render as raw LaTeX]** → Documented limitation. WeasyPrint cannot execute JavaScript, so KaTeX/MathJax expressions will not render visually. Mitigate by clearly stating this in the tool's docstring and suggesting users use SiYuan's desktop app for math-heavy documents.

**[SiYuan's exportPreviewHTML is undocumented]** → The endpoint could change across SiYuan versions. Mitigate by pinning the expected response shape in tests and failing fast with a clear error if the response format changes.

**[CSS rendering differences]** → WeasyPrint may not render SiYuan's CSS identically to a browser. Most standard layouts will work fine, but edge cases with complex CSS selectors or pseudo-elements may differ. Mitigate by testing with diverse real-world SiYuan documents.

**[System dependency in Docker]** → Pango/Cairo are system packages that must be installed in the Docker image. Mitigate by pinning the `apt` package versions and documenting the dependency.

## Open Questions

1. **Does `exportPreviewHTML` with `image=true` already embed images as data URIs?** — If yes, WeasyPrint can render them directly. If not, `base_url` pointing to SiYuan should allow WeasyPrint to fetch them. Needs investigation during implementation.
2. **Which SiYuan export endpoint works best with WeasyPrint?** — `exportPreviewHTML` is designed for PDF preview and may include JS-dependent elements. `exportHTML` with `pdf=true` might produce cleaner static HTML. Test both during implementation.
