"""PDF generation utilities for normalized document output."""

from io import BytesIO
from datetime import datetime
from typing import Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER


def generate_pdf(
    title: str,
    source_filename: str,
    category: str,
    extraction_timestamp: str,
    body_text: str,
    document_id: Optional[str] = None
) -> bytes:
    """
    Generate a normalized PDF document from extracted text.

    Args:
        title: Document title
        source_filename: Original source filename
        category: Document classification category
        extraction_timestamp: ISO8601 timestamp of extraction
        body_text: Normalized document body text
        document_id: Optional unique document identifier

    Returns:
        PDF file as bytes

    Example:
        >>> pdf_bytes = generate_pdf(
        ...     title="System Architecture Spec",
        ...     source_filename="arch_spec_v2.docx",
        ...     category="technical-spec",
        ...     extraction_timestamp="2026-03-24T12:00:00.000Z",
        ...     body_text="This document describes..."
        ... )
    """
    buffer = BytesIO()

    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=1.0 * inch,
        bottomMargin=0.75 * inch,
    )

    # Build content
    story = []
    styles = _get_styles()

    # Title
    story.append(Paragraph(title, styles["DocTitle"]))
    story.append(Spacer(1, 0.3 * inch))

    # Metadata section
    metadata_lines = [
        f"<b>Source:</b> {_escape_html(source_filename)}",
        f"<b>Category:</b> {_escape_html(category)}",
        f"<b>Extracted:</b> {_format_timestamp(extraction_timestamp)}",
    ]
    if document_id:
        metadata_lines.append(f"<b>Document ID:</b> {_escape_html(document_id)}")

    for line in metadata_lines:
        story.append(Paragraph(line, styles["Metadata"]))

    story.append(Spacer(1, 0.4 * inch))

    # Separator
    story.append(Paragraph("─" * 80, styles["Separator"]))
    story.append(Spacer(1, 0.3 * inch))

    # Body text - split into paragraphs
    paragraphs = body_text.split("\n\n")
    for para_text in paragraphs:
        if para_text.strip():
            # Escape HTML and preserve line breaks within paragraphs
            escaped_text = _escape_html(para_text.strip())
            escaped_text = escaped_text.replace("\n", "<br/>")
            story.append(Paragraph(escaped_text, styles["Body"]))
            story.append(Spacer(1, 0.15 * inch))

    # Build PDF
    doc.build(story)

    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


def _get_styles():
    """Create and return custom paragraph styles for the PDF."""
    styles = getSampleStyleSheet()

    # Custom title style (using unique name to avoid conflicts)
    styles.add(ParagraphStyle(
        name="DocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor="#1a1a1a",
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    ))

    # Metadata style
    styles.add(ParagraphStyle(
        name="Metadata",
        parent=styles["Normal"],
        fontSize=10,
        textColor="#4a4a4a",
        spaceAfter=4,
        fontName="Helvetica",
    ))

    # Separator style
    styles.add(ParagraphStyle(
        name="Separator",
        parent=styles["Normal"],
        fontSize=8,
        textColor="#cccccc",
        alignment=TA_CENTER,
    ))

    # Body text style
    styles.add(ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor="#1a1a1a",
        fontName="Helvetica",
        alignment=TA_LEFT,
        firstLineIndent=0,
    ))

    return styles


def _escape_html(text: str) -> str:
    """
    Escape HTML special characters for ReportLab.

    ReportLab's Paragraph uses a subset of HTML tags, so we need to escape
    special characters that shouldn't be interpreted as markup.
    """
    if not text:
        return ""

    replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }

    for char, escape in replacements.items():
        text = text.replace(char, escape)

    return text


def _format_timestamp(iso_timestamp: str) -> str:
    """
    Format ISO8601 timestamp to human-readable format.

    Args:
        iso_timestamp: ISO8601 formatted timestamp string

    Returns:
        Formatted timestamp like "March 24, 2026 at 12:00 PM UTC"
    """
    try:
        # Parse ISO8601 format
        if iso_timestamp.endswith("Z"):
            dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(iso_timestamp)

        # Format as readable string
        return dt.strftime("%B %d, %Y at %I:%M %p UTC")
    except (ValueError, AttributeError):
        # If parsing fails, return original
        return iso_timestamp
