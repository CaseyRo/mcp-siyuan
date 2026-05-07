## ADDED Requirements

### Requirement: Export document as PDF
The system SHALL expose a `siyuan_export_pdf` MCP tool that accepts a SiYuan document ID and returns a PDF rendering of that document. The tool SHALL fetch pre-rendered HTML from SiYuan's `/api/export/exportPreviewHTML` endpoint and convert it to PDF using a server-side renderer.

#### Scenario: Basic document export
- **WHEN** the tool is called with a valid document ID and no additional options
- **THEN** the system returns a base64-encoded PDF of the document rendered in A4 portrait orientation

#### Scenario: Invalid document ID
- **WHEN** the tool is called with a non-existent document ID
- **THEN** the system raises a descriptive error indicating the document was not found

#### Scenario: SiYuan unreachable
- **WHEN** the tool is called but SiYuan's API is not reachable
- **THEN** the system raises a connection error via the existing `SiYuanClient` error handling

### Requirement: Configurable page orientation
The tool SHALL accept an `orientation` parameter with values `portrait` (default) or `landscape`.

#### Scenario: Portrait orientation
- **WHEN** the tool is called with `orientation="portrait"` or no orientation specified
- **THEN** the PDF is rendered in portrait layout

#### Scenario: Landscape orientation
- **WHEN** the tool is called with `orientation="landscape"`
- **THEN** the PDF is rendered in landscape layout

### Requirement: Configurable page size
The tool SHALL accept a `page_size` parameter supporting both EU and US standard paper sizes. The default SHALL be `A4`.

#### Scenario: EU paper sizes
- **WHEN** the tool is called with `page_size` set to `A3`, `A4`, or `A5`
- **THEN** the PDF is rendered at the corresponding ISO 216 dimensions

#### Scenario: US paper sizes
- **WHEN** the tool is called with `page_size` set to `Letter`, `Legal`, or `Tabloid`
- **THEN** the PDF is rendered at the corresponding US standard dimensions (Letter: 8.5x11in, Legal: 8.5x14in, Tabloid: 11x17in)

#### Scenario: Invalid page size
- **WHEN** the tool is called with an unsupported `page_size` value
- **THEN** the system raises a validation error listing the supported sizes

### Requirement: Image optimisation
The tool SHALL accept an `image_quality` parameter (integer 1-100, default 85) that controls JPEG compression of embedded images to manage PDF file size.

#### Scenario: Default image quality
- **WHEN** the tool is called with no `image_quality` specified
- **THEN** embedded images are compressed at quality 85

#### Scenario: Low quality for smaller file size
- **WHEN** the tool is called with `image_quality=40`
- **THEN** embedded images are compressed at quality 40, producing a noticeably smaller PDF

#### Scenario: Maximum quality
- **WHEN** the tool is called with `image_quality=100`
- **THEN** embedded images are included at original quality with no lossy compression

#### Scenario: Invalid quality value
- **WHEN** the tool is called with `image_quality` outside range 1-100
- **THEN** the system raises a validation error

### Requirement: Diverse block type rendering
The PDF output SHALL faithfully render all major SiYuan block types as produced by SiYuan's `exportPreviewHTML` endpoint. The rendering fidelity depends on SiYuan's HTML output; the PDF renderer MUST NOT strip or break the existing styling.

#### Scenario: Text content blocks
- **WHEN** a document contains headings, paragraphs, lists, and blockquotes
- **THEN** the PDF renders each block type with appropriate visual hierarchy and styling

#### Scenario: Code blocks
- **WHEN** a document contains fenced code blocks
- **THEN** the PDF renders them with monospace font and preserves syntax highlighting if present in the HTML

#### Scenario: Math blocks (known limitation)
- **WHEN** a document contains KaTeX/MathJax math expressions
- **THEN** the PDF renders the raw LaTeX source text (math rendering requires JavaScript which WeasyPrint does not support; this SHALL be documented in the tool description)

#### Scenario: Tables
- **WHEN** a document contains tables
- **THEN** the PDF renders tables with borders and proper column alignment, handling tables wider than page width gracefully (scaling or horizontal overflow)

#### Scenario: Embedded images
- **WHEN** a document contains embedded images
- **THEN** the PDF includes the images, scaled to fit within page margins, and compressed per the `image_quality` setting

#### Scenario: Long documents
- **WHEN** a document spans many pages
- **THEN** the PDF renders all content across multiple pages with proper page breaks (avoiding breaks mid-paragraph or mid-table where possible)

#### Scenario: Short documents
- **WHEN** a document is only a few lines
- **THEN** the PDF renders as a single page without excessive blank space

### Requirement: Output format
The tool SHALL return the PDF as a base64-encoded string by default. The response SHALL include the document name (derived from SiYuan's document title) for use as a filename.

#### Scenario: Default output
- **WHEN** the tool is called with default options
- **THEN** the response contains `name` (string, document title) and `pdf_base64` (string, base64-encoded PDF content)

#### Scenario: Large document output
- **WHEN** the generated PDF exceeds 10MB
- **THEN** the response includes a `warning` field indicating the file is large
