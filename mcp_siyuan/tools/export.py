"""Export tools for SiYuan — PDF generation via WeasyPrint."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from fastmcp.utilities.types import File
from pydantic import Field

from mcp_siyuan.client import SiYuanError, sy
from mcp_siyuan.config import settings

logger = logging.getLogger(__name__)

_SIYUAN_ID_RE = re.compile(r"^\d{14}-[a-z0-9]{7}$")
_MAX_HTML_BYTES = 20 * 1024 * 1024  # 20 MB
_LARGE_PDF_THRESHOLD = 10 * 1024 * 1024  # 10 MB

PAGE_SIZES: dict[str, tuple[float, float]] = {
    "A3": (297, 420),
    "A4": (210, 297),
    "A5": (148, 210),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
    "Tabloid": (279.4, 431.8),
}


def _validate_id(id: str) -> str:
    """Validate a SiYuan block ID format."""
    if not _SIYUAN_ID_RE.match(id):
        raise ValueError(
            f"Invalid SiYuan block ID format: {id!r}. "
            "Expected format: YYYYMMDDHHMMSS-xxxxxxx (e.g. 20210808180320-fqgskfj)"
        )
    return id


def _check_url_allowed(url: str) -> None:
    """Raise ValueError if url is not a data URI or on the SiYuan origin."""
    parsed = urlparse(url)
    if parsed.scheme == "data":
        return
    allowed = urlparse(settings.siyuan_url)
    if parsed.scheme != allowed.scheme or parsed.netloc != allowed.netloc:
        raise ValueError(f"Blocked fetch to disallowed origin: {parsed.netloc}")


def _restricted_fetcher(url: str, timeout: int = 10, ssl_context: Any = None) -> dict:
    """URL fetcher that only allows data URIs and SiYuan-origin fetches."""
    from weasyprint import default_url_fetcher

    _check_url_allowed(url)
    return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)


_PRINT_CSS = """
/* Page layout */
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans", sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
}

/* Hide Protyle editor chrome */
.protyle-attr,
.protyle-action,
[contenteditable] { display: contents !important; }

/* Headings */
.h1 > div:first-child { font-size: 22pt; font-weight: 700; margin: 18pt 0 8pt; }
.h2 > div:first-child { font-size: 17pt; font-weight: 700; margin: 14pt 0 6pt; }
.h3 > div:first-child { font-size: 14pt; font-weight: 700; margin: 12pt 0 5pt; }
.h4 > div:first-child { font-size: 12pt; font-weight: 700; margin: 10pt 0 4pt; }
.h5 > div:first-child { font-size: 11pt; font-weight: 700; margin: 8pt 0 3pt; }
.h6 > div:first-child { font-size: 10pt; font-weight: 700; margin: 8pt 0 3pt; }
.h1, .h2, .h3, .h4, .h5, .h6 {
    padding: 0 !important; margin: 0 !important;
    page-break-after: avoid;
}

/* Paragraphs */
.p { padding: 0 !important; margin: 0 0 6pt !important; }

/* Lists */
.list { padding: 0 0 0 18pt !important; margin: 0 0 6pt !important; }
.list[data-subtype="u"] { list-style-type: disc; display: block; }
.list[data-subtype="o"] { list-style-type: decimal; display: block; }
.li { display: list-item; padding: 0 !important; margin: 0 0 3pt !important; }
.li .list { margin: 3pt 0 0 !important; }

/* Blockquote */
.bq {
    border-left: 3pt solid #ccc; padding: 4pt 0 4pt 12pt !important;
    margin: 6pt 0 !important; color: #555;
}

/* Horizontal rule */
.hr { border: none; border-top: 1pt solid #ddd; margin: 10pt 0 !important; padding: 0 !important; }
.hr > div { display: none; }

/* Code blocks */
.code-block {
    background: #f5f5f5; padding: 8pt 10pt !important; margin: 6pt 0 !important;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 9pt; line-height: 1.5; border-radius: 4pt;
    white-space: pre-wrap; word-break: break-all;
}
.code-block .protyle-action { display: none !important; }

/* Tables */
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 10pt; }
th, td { border: 0.5pt solid #ccc; padding: 4pt 8pt; text-align: left; }
th { background: #f5f5f5; font-weight: 600; }

/* Super block */
.sb { padding: 0 !important; margin: 0 !important; }

/* Bold / emphasis */
[data-type="strong"] { font-weight: 700; }
[data-type="em"] { font-style: italic; }

/* Links */
a { color: #1a73e8; text-decoration: none; }

/* Images */
img { max-width: 100%; height: auto; }

/* Avoid page breaks inside blocks */
.p, .li, .code-block, table { page-break-inside: avoid; }
"""


def _page_css(page_size: str, orientation: str) -> str:
    """Generate @page CSS for the given size and orientation."""
    width, height = PAGE_SIZES[page_size]
    if orientation == "landscape":
        width, height = height, width
    return f"@page {{ size: {width}mm {height}mm; margin: 15mm; }}\n{_PRINT_CSS}"


async def _get_preview_html(id: str) -> tuple[str, str]:
    """Fetch rendered HTML from SiYuan's export preview endpoint."""
    data = await sy.call(
        "/api/export/exportPreviewHTML",
        id=id,
        keepFold=False,
        merge=False,
        image=True,
    )
    if not data:
        raise SiYuanError(f"Document {id} not found or empty")
    name = data.get("name", "export")
    content = data.get("content", "")
    return name, content


def _render_pdf(
    html: str,
    orientation: str,
    page_size: str,
    image_quality: int,
) -> bytes:
    """Convert HTML to PDF bytes using WeasyPrint."""
    from weasyprint import CSS, HTML

    css = _page_css(page_size, orientation)
    try:
        pdf_bytes = HTML(
            string=html,
            base_url=settings.siyuan_url,
        ).write_pdf(
            stylesheets=[CSS(string=css)],
            url_fetcher=_restricted_fetcher,
            optimize_images=True,
            jpeg_quality=image_quality,
        )
    except Exception as exc:
        logger.error("WeasyPrint rendering failed: %s", exc)
        raise SiYuanError("PDF rendering failed. Check server logs for details.") from exc
    return pdf_bytes


async def siyuan_export_pdf(
    id: str,
    orientation: Annotated[
        Literal["portrait", "landscape"],
        Field(description="Page orientation"),
    ] = "portrait",
    page_size: Annotated[
        Literal["A3", "A4", "A5", "Letter", "Legal", "Tabloid"],
        Field(description="Paper size — EU (A3/A4/A5) or US (Letter/Legal/Tabloid)"),
    ] = "A4",
    image_quality: Annotated[
        int,
        Field(ge=1, le=100, description="JPEG quality for embedded images (1-100)"),
    ] = 85,
):
    """Export a SiYuan document as PDF.

    Returns the PDF as a downloadable file alongside a text summary.

    Known limitation: Math blocks (KaTeX/MathJax) render as raw LaTeX text
    because the PDF renderer does not execute JavaScript. Use SiYuan's
    desktop app for math-heavy documents.

    Args:
        id: The document block ID to export.
        orientation: Page orientation — portrait (default) or landscape.
        page_size: Paper size — A3, A4 (default), A5, Letter, Legal, or Tabloid.
        image_quality: JPEG compression quality for embedded images (1-100, default 85).
            Lower values produce smaller files.
    """
    _validate_id(id)

    name, html = await _get_preview_html(id)

    html_size = len(html.encode("utf-8"))
    if html_size > _MAX_HTML_BYTES:
        raise ValueError(
            f"Document HTML is too large ({html_size // (1024 * 1024)} MB, "
            f"limit {_MAX_HTML_BYTES // (1024 * 1024)} MB). "
            "Use SiYuan's desktop app for very large documents."
        )

    pdf_bytes = _render_pdf(html, orientation, page_size, image_quality)
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    size_kb = len(pdf_bytes) // 1024

    result: list = [
        File(data=pdf_bytes, format="pdf", name=name),
    ]

    summary = f"Generated PDF: {name}.pdf ({size_kb} KB, {page_size} {orientation}, sha256: {pdf_sha256})"
    if len(pdf_bytes) > _LARGE_PDF_THRESHOLD:
        summary += f"\n⚠ PDF is large ({len(pdf_bytes) // (1024 * 1024)} MB). Consider reducing image_quality."

    result.append(summary)
    return result
