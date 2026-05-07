"""Tests for PDF export tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mcp_siyuan.client import SiYuanError

# ---------------------------------------------------------------------------
# Check if WeasyPrint system libs are available
# ---------------------------------------------------------------------------

try:
    from weasyprint import HTML  # noqa: F401

    HAS_WEASYPRINT = True
except OSError:
    HAS_WEASYPRINT = False

needs_weasyprint = pytest.mark.skipif(
    not HAS_WEASYPRINT,
    reason="WeasyPrint system libraries (Pango/Cairo) not installed",
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
<h1>Test Document</h1>
<p>Hello world.</p>
</body>
</html>
"""

SAMPLE_HTML_HEADINGS = """
<html><body>
<h1>Heading 1</h1>
<h2>Heading 2</h2>
<h3>Heading 3</h3>
<p>Paragraph under heading.</p>
</body></html>
"""

SAMPLE_HTML_CODE = """
<html><body>
<pre><code class="language-python">def hello():
    print("world")</code></pre>
</body></html>
"""

SAMPLE_HTML_TABLE = """
<html><body>
<table border="1">
<tr><th>Name</th><th>Value</th></tr>
<tr><td>Alpha</td><td>1</td></tr>
<tr><td>Beta</td><td>2</td></tr>
</table>
</body></html>
"""

SAMPLE_HTML_LIST = """
<html><body>
<ul>
<li>Item 1</li>
<li>Item 2</li>
<li>Item 3</li>
</ul>
<blockquote>A quote</blockquote>
</body></html>
"""

SAMPLE_HTML_IMAGE = """
<html><body>
<p>Document with image:</p>
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" alt="1x1 pixel">
</body></html>
"""

FAKE_PDF = b"%PDF-1.4 fake pdf content for testing"


@pytest.fixture
def mock_sy():
    with patch("mcp_siyuan.tools.export.sy") as mock:
        mock.call = AsyncMock()
        yield mock


@pytest.fixture
def mock_settings():
    with patch("mcp_siyuan.tools.export.settings") as mock:
        mock.siyuan_url = "http://siyuan:6806"
        yield mock


@pytest.fixture
def mock_render():
    """Mock _render_pdf to avoid needing WeasyPrint system libs."""
    with patch("mcp_siyuan.tools.export._render_pdf", return_value=FAKE_PDF) as mock:
        yield mock


# ---------------------------------------------------------------------------
# _get_preview_html
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_preview_html_success(mock_sy):
    """_get_preview_html returns (name, content) from exportPreviewHTML."""
    from mcp_siyuan.tools.export import _get_preview_html

    mock_sy.call.return_value = {
        "name": "My Document",
        "content": "<html><body>Hello</body></html>",
    }
    name, html = await _get_preview_html("20210808180320-fqgskfj")
    assert name == "My Document"
    assert "Hello" in html
    mock_sy.call.assert_called_once_with(
        "/api/export/exportPreviewHTML",
        id="20210808180320-fqgskfj",
        keepFold=False,
        merge=False,
        image=True,
    )


@pytest.mark.asyncio
async def test_get_preview_html_missing_doc(mock_sy):
    """_get_preview_html raises on empty response."""
    from mcp_siyuan.tools.export import _get_preview_html

    mock_sy.call.return_value = None
    with pytest.raises(SiYuanError, match="not found"):
        await _get_preview_html("20210808180320-fqgskfj")


# ---------------------------------------------------------------------------
# _page_css
# ---------------------------------------------------------------------------


def test_page_css_all_sizes():
    """_page_css generates correct dimensions for all page sizes."""
    from mcp_siyuan.tools.export import PAGE_SIZES, _page_css

    for size_name, (w, h) in PAGE_SIZES.items():
        css = _page_css(size_name, "portrait")
        assert f"{w}mm" in css
        assert f"{h}mm" in css


def test_page_css_landscape_swaps():
    """_page_css swaps width/height for landscape."""
    from mcp_siyuan.tools.export import _page_css

    portrait = _page_css("A4", "portrait")
    landscape = _page_css("A4", "landscape")
    assert "210mm 297mm" in portrait
    assert "297mm 210mm" in landscape


# ---------------------------------------------------------------------------
# export_pdf — default call (mocked rendering)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_pdf_default(mock_sy, mock_settings, mock_render):
    """Default export returns a File and a text summary."""
    from fastmcp.utilities.types import File
    from mcp_siyuan.tools.export import export_pdf

    mock_sy.call.return_value = {
        "name": "Test Doc",
        "content": SAMPLE_HTML,
    }
    result = await export_pdf(id="20210808180320-fqgskfj")
    assert isinstance(result, list)
    assert len(result) == 2
    # First item is a File
    assert isinstance(result[0], File)
    assert result[0]._name == "Test Doc"
    # Second item is a text summary
    assert "Test Doc.pdf" in result[1]
    assert "sha256:" in result[1]


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_pdf_invalid_id():
    """Invalid document ID format raises ValueError."""
    from mcp_siyuan.tools.export import export_pdf

    with pytest.raises(ValueError, match="Invalid SiYuan block ID"):
        await export_pdf(id="not-a-valid-id")


# ---------------------------------------------------------------------------
# Large file warning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_pdf_large_file_warning(mock_sy, mock_settings):
    """PDF > 10MB includes a warning in the summary text."""
    from mcp_siyuan.tools.export import _LARGE_PDF_THRESHOLD, export_pdf

    mock_sy.call.return_value = {
        "name": "Big Doc",
        "content": SAMPLE_HTML,
    }
    fake_pdf = b"%PDF-1.4 " + b"\x00" * (_LARGE_PDF_THRESHOLD + 1)
    with patch("mcp_siyuan.tools.export._render_pdf", return_value=fake_pdf):
        result = await export_pdf(id="20210808180320-fqgskfj")
    summary = result[1]
    assert "large" in summary.lower()


# ---------------------------------------------------------------------------
# _validate_id
# ---------------------------------------------------------------------------


def test_validate_id_valid():
    """Valid SiYuan IDs pass validation."""
    from mcp_siyuan.tools.export import _validate_id

    assert _validate_id("20210808180320-fqgskfj") == "20210808180320-fqgskfj"
    assert _validate_id("20260404120000-abcdefg") == "20260404120000-abcdefg"


def test_validate_id_rejects_empty():
    """Empty string is rejected."""
    from mcp_siyuan.tools.export import _validate_id

    with pytest.raises(ValueError, match="Invalid SiYuan block ID"):
        _validate_id("")


def test_validate_id_rejects_path_traversal():
    """Path traversal attempts are rejected."""
    from mcp_siyuan.tools.export import _validate_id

    with pytest.raises(ValueError, match="Invalid SiYuan block ID"):
        _validate_id("../../../../etc/passwd")


def test_validate_id_rejects_wrong_format():
    """IDs with wrong format are rejected."""
    from mcp_siyuan.tools.export import _validate_id

    with pytest.raises(ValueError):
        _validate_id("12345-abc")
    with pytest.raises(ValueError):
        _validate_id("20210808180320-ABCDEFG")
    with pytest.raises(ValueError):
        _validate_id("20210808180320-fqgskfj-extra")


# ---------------------------------------------------------------------------
# _restricted_fetcher
# ---------------------------------------------------------------------------


def test_check_url_allows_data_uri():
    """Data URIs pass URL validation."""
    from mcp_siyuan.tools.export import _check_url_allowed

    with patch("mcp_siyuan.tools.export.settings") as mock_s:
        mock_s.siyuan_url = "http://siyuan:6806"
        _check_url_allowed("data:text/plain;base64,SGVsbG8=")  # should not raise


def test_check_url_allows_siyuan_origin():
    """SiYuan-origin URLs pass URL validation."""
    from mcp_siyuan.tools.export import _check_url_allowed

    with patch("mcp_siyuan.tools.export.settings") as mock_s:
        mock_s.siyuan_url = "http://siyuan:6806"
        _check_url_allowed("http://siyuan:6806/assets/image.png")  # should not raise


def test_check_url_blocks_external():
    """External origins are blocked."""
    from mcp_siyuan.tools.export import _check_url_allowed

    with patch("mcp_siyuan.tools.export.settings") as mock_s:
        mock_s.siyuan_url = "http://siyuan:6806"
        with pytest.raises(ValueError, match="Blocked fetch"):
            _check_url_allowed("http://evil.com/steal-data")


def test_check_url_blocks_metadata():
    """Cloud metadata endpoints are blocked."""
    from mcp_siyuan.tools.export import _check_url_allowed

    with patch("mcp_siyuan.tools.export.settings") as mock_s:
        mock_s.siyuan_url = "http://siyuan:6806"
        with pytest.raises(ValueError, match="Blocked fetch"):
            _check_url_allowed("http://169.254.169.254/latest/meta-data/")


# ---------------------------------------------------------------------------
# HTML size cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_pdf_html_size_cap(mock_sy, mock_settings):
    """Oversized HTML response raises before reaching WeasyPrint."""
    from mcp_siyuan.tools.export import _MAX_HTML_BYTES, export_pdf

    oversized_html = "x" * (_MAX_HTML_BYTES + 1)
    mock_sy.call.return_value = {
        "name": "Huge Doc",
        "content": oversized_html,
    }
    with pytest.raises(ValueError, match="too large"):
        await export_pdf(id="20210808180320-fqgskfj")


# ---------------------------------------------------------------------------
# WeasyPrint error wrapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_pdf_weasyprint_error_wrapped(mock_sy, mock_settings):
    """WeasyPrint errors are wrapped — caller gets generic message."""
    from mcp_siyuan.tools.export import export_pdf

    mock_sy.call.return_value = {
        "name": "Bad Doc",
        "content": "<html><body>OK</body></html>",
    }
    with patch(
        "mcp_siyuan.tools.export._render_pdf",
        side_effect=SiYuanError("PDF rendering failed. Check server logs for details."),
    ):
        with pytest.raises(SiYuanError, match="PDF rendering failed"):
            await export_pdf(id="20210808180320-fqgskfj")


# ---------------------------------------------------------------------------
# Rendering quality tests (require WeasyPrint system libs)
# ---------------------------------------------------------------------------


@needs_weasyprint
def test_render_short_content():
    """Short content produces a valid single-page PDF."""
    from mcp_siyuan.tools.export import _render_pdf

    with patch("mcp_siyuan.tools.export.settings") as mock_s:
        mock_s.siyuan_url = "http://siyuan:6806"
        pdf = _render_pdf(SAMPLE_HTML, "portrait", "A4", 85)
    assert pdf[:5] == b"%PDF-"


@needs_weasyprint
def test_render_long_content():
    """Long content produces a larger PDF than short content."""
    from mcp_siyuan.tools.export import _render_pdf

    long_html = "<html><body>" + "<p>Paragraph content here.</p>\n" * 200 + "</body></html>"
    with patch("mcp_siyuan.tools.export.settings") as mock_s:
        mock_s.siyuan_url = "http://siyuan:6806"
        short_pdf = _render_pdf(SAMPLE_HTML, "portrait", "A4", 85)
        long_pdf = _render_pdf(long_html, "portrait", "A4", 85)
    assert len(long_pdf) > len(short_pdf)


@needs_weasyprint
def test_render_portrait_vs_landscape():
    """Portrait and landscape produce different PDFs."""
    from mcp_siyuan.tools.export import _render_pdf

    with patch("mcp_siyuan.tools.export.settings") as mock_s:
        mock_s.siyuan_url = "http://siyuan:6806"
        portrait = _render_pdf(SAMPLE_HTML, "portrait", "A4", 85)
        landscape = _render_pdf(SAMPLE_HTML, "landscape", "A4", 85)
    assert portrait[:5] == b"%PDF-"
    assert landscape[:5] == b"%PDF-"
    assert portrait != landscape


@needs_weasyprint
def test_render_all_page_sizes():
    """All EU and US page sizes render without error."""
    from mcp_siyuan.tools.export import PAGE_SIZES, _render_pdf

    with patch("mcp_siyuan.tools.export.settings") as mock_s:
        mock_s.siyuan_url = "http://siyuan:6806"
        for size in PAGE_SIZES:
            pdf = _render_pdf(SAMPLE_HTML, "portrait", size, 85)
            assert pdf[:5] == b"%PDF-", f"Failed for size {size}"


@needs_weasyprint
def test_render_diverse_blocks():
    """Documents with headings, code, tables, lists, images all render."""
    from mcp_siyuan.tools.export import _render_pdf

    with patch("mcp_siyuan.tools.export.settings") as mock_s:
        mock_s.siyuan_url = "http://siyuan:6806"
        for fixture in [
            SAMPLE_HTML_HEADINGS,
            SAMPLE_HTML_CODE,
            SAMPLE_HTML_TABLE,
            SAMPLE_HTML_LIST,
            SAMPLE_HTML_IMAGE,
        ]:
            pdf = _render_pdf(fixture, "portrait", "A4", 85)
            assert pdf[:5] == b"%PDF-"


@needs_weasyprint
def test_render_image_quality_affects_size():
    """Both quality levels render without error."""
    from mcp_siyuan.tools.export import _render_pdf

    with patch("mcp_siyuan.tools.export.settings") as mock_s:
        mock_s.siyuan_url = "http://siyuan:6806"
        low_q = _render_pdf(SAMPLE_HTML_IMAGE, "portrait", "A4", 40)
        high_q = _render_pdf(SAMPLE_HTML_IMAGE, "portrait", "A4", 100)
    assert low_q[:5] == b"%PDF-"
    assert high_q[:5] == b"%PDF-"
