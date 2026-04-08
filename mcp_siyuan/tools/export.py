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
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans", sans-serif;
    font-size: 11pt; line-height: 1.6; color: #1a1a1a;
}
h1 { font-size: 22pt; margin: 18pt 0 8pt; }
h2 { font-size: 17pt; margin: 14pt 0 6pt; }
h3 { font-size: 14pt; margin: 12pt 0 5pt; }
h4 { font-size: 12pt; margin: 10pt 0 4pt; }
h5 { font-size: 11pt; margin: 8pt 0 3pt; }
h6 { font-size: 10pt; margin: 8pt 0 3pt; }
h1, h2, h3, h4, h5, h6 { page-break-after: avoid; }
p { margin: 0 0 6pt; }
ul, ol { padding-left: 20pt; margin: 0 0 6pt; }
li { margin: 0 0 2pt; }
blockquote {
    border-left: 3pt solid #ccc; padding: 4pt 0 4pt 12pt;
    margin: 6pt 0; color: #555;
}
hr { border: none; border-top: 1pt solid #ddd; margin: 10pt 0; }
pre {
    background: #f5f5f5; padding: 8pt 10pt; margin: 6pt 0;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 9pt; line-height: 1.5; border-radius: 4pt;
    white-space: pre-wrap; word-break: break-all;
}
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 10pt; }
th, td { border: 0.5pt solid #ccc; padding: 4pt 8pt; text-align: left; }
th { background: #f5f5f5; font-weight: 600; }
a { color: #1a73e8; text-decoration: none; }
img { max-width: 100%; height: auto; }
p, li, pre, table { page-break-inside: avoid; }
"""


def _protyle_to_html(protyle_html: str) -> str:
    """Convert SiYuan Protyle editor HTML to clean semantic HTML."""
    from html.parser import HTMLParser
    from io import StringIO

    class ProtyleConverter(HTMLParser):
        def __init__(self):
            super().__init__()
            self.out = StringIO()
            self.skip_depth = 0  # depth of elements being skipped
            self.tag_stack: list[str] = []

        def _write(self, s: str) -> None:
            if self.skip_depth == 0:
                self.out.write(s)

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attr_dict = dict(attrs)
            classes = (attr_dict.get("class") or "").split()

            # Skip editor chrome entirely
            if "protyle-attr" in classes or "protyle-action" in classes:
                self.skip_depth += 1
                return

            if self.skip_depth > 0:
                self.skip_depth += 1
                return

            dtype = attr_dict.get("data-type", "")
            subtype = attr_dict.get("data-subtype", "")

            # Map Protyle blocks to semantic HTML
            if dtype == "NodeHeading":
                level = subtype if subtype in ("h1", "h2", "h3", "h4", "h5", "h6") else "h2"
                self._write(f"<{level}>")
                self.tag_stack.append(level)
                return

            if dtype == "NodeParagraph":
                self._write("<p>")
                self.tag_stack.append("p")
                return

            if dtype == "NodeList":
                list_tag = "ol" if subtype == "o" else "ul"
                self._write(f"<{list_tag}>")
                self.tag_stack.append(list_tag)
                return

            if dtype == "NodeListItem":
                self._write("<li>")
                self.tag_stack.append("li")
                return

            if dtype == "NodeBlockquote" or "bq" in classes:
                self._write("<blockquote>")
                self.tag_stack.append("blockquote")
                return

            if dtype == "NodeThematicBreak" or "hr" in classes:
                self._write("<hr>")
                self.tag_stack.append("hr")
                return

            if dtype == "NodeCodeBlock" or "code-block" in classes:
                self._write("<pre><code>")
                self.tag_stack.append("code-block")
                return

            if dtype == "NodeSuperBlock" or "sb" in classes:
                self._write("<div>")
                self.tag_stack.append("div")
                return

            # Inline elements
            if tag == "span":
                stype = attr_dict.get("data-type", "")
                if stype == "strong":
                    self._write("<strong>")
                    self.tag_stack.append("strong")
                    return
                if stype == "em":
                    self._write("<em>")
                    self.tag_stack.append("em")
                    return
                if stype == "code" or stype == "inline-code":
                    self._write("<code>")
                    self.tag_stack.append("code")
                    return
                if stype == "a" or stype == "block-ref":
                    href = attr_dict.get("data-href", "")
                    self._write(f'<a href="{href}">')
                    self.tag_stack.append("a")
                    return
                # Pass through other spans
                self._write("<span>")
                self.tag_stack.append("span")
                return

            if tag == "a":
                href = attr_dict.get("href", "")
                # Skip pdf-outline links
                if href.startswith("pdf-outline://"):
                    self.skip_depth += 1
                    return
                self._write(f'<a href="{href}">')
                self.tag_stack.append("a")
                return

            if tag == "img":
                src = attr_dict.get("src", "")
                alt = attr_dict.get("alt", "")
                self._write(f'<img src="{src}" alt="{alt}">')
                return

            if tag == "table":
                self._write("<table>")
                self.tag_stack.append("table")
                return
            if tag in ("thead", "tbody", "tr", "th", "td"):
                extra = ""
                if tag in ("th", "td"):
                    colspan = attr_dict.get("colspan")
                    rowspan = attr_dict.get("rowspan")
                    if colspan:
                        extra += f' colspan="{colspan}"'
                    if rowspan:
                        extra += f' rowspan="{rowspan}"'
                self._write(f"<{tag}{extra}>")
                self.tag_stack.append(tag)
                return

            if tag == "br":
                self._write("<br>")
                return

            # Contenteditable divs — just pass through content
            if tag == "div":
                self.tag_stack.append("_div")
                return

            # Default: pass through
            self.tag_stack.append(f"_{tag}")

        def handle_endtag(self, tag: str) -> None:
            if self.skip_depth > 0:
                self.skip_depth -= 1
                return

            if not self.tag_stack:
                return

            mapped = self.tag_stack.pop()

            if mapped == "code-block":
                self._write("</code></pre>")
            elif mapped == "hr":
                pass  # self-closing
            elif mapped.startswith("_"):
                pass  # skip unmapped wrappers
            else:
                self._write(f"</{mapped}>")

        def handle_data(self, data: str) -> None:
            self._write(data)

        def handle_entityref(self, name: str) -> None:
            self._write(f"&{name};")

        def handle_charref(self, name: str) -> None:
            self._write(f"&#{name};")

        def get_result(self) -> str:
            return self.out.getvalue()

    converter = ProtyleConverter()
    converter.feed(protyle_html)
    body = converter.get_result()

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body>{body}</body></html>"""


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
    """Convert Protyle HTML to PDF bytes using WeasyPrint."""
    from weasyprint import CSS, HTML

    clean_html = _protyle_to_html(html)
    css = _page_css(page_size, orientation)
    try:
        pdf_bytes = HTML(
            string=clean_html,
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


async def export_pdf(
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
    """[notes] Export a SiYuan document as PDF.

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
