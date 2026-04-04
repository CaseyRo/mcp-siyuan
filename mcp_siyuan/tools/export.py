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


def _page_css(page_size: str, orientation: str) -> str:
    """Generate @page CSS for the given size and orientation."""
    width, height = PAGE_SIZES[page_size]
    if orientation == "landscape":
        width, height = height, width
    return f"@page {{ size: {width}mm {height}mm; margin: 15mm; }}"


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
) -> list:
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
        File(data=pdf_bytes, format="pdf", name=f"{name}.pdf"),
    ]

    summary = f"Generated PDF: {name}.pdf ({size_kb} KB, {page_size} {orientation}, sha256: {pdf_sha256})"
    if len(pdf_bytes) > _LARGE_PDF_THRESHOLD:
        summary += f"\n⚠ PDF is large ({len(pdf_bytes) // (1024 * 1024)} MB). Consider reducing image_quality."

    result.append(summary)
    return result
