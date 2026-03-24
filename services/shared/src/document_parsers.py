"""
Document parsing utilities for multiple file formats.

Supports: PDF, images (PNG/JPG), DOCX, TXT, CSV
"""

import io
import csv
import mimetypes
from typing import Dict, Any, Optional
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

try:
    from PIL import Image
except ImportError:
    Image = None


class DocumentParser:
    """Factory for creating appropriate parsers based on file type."""

    SUPPORTED_EXTENSIONS = {
        '.pdf': 'pdf',
        '.png': 'image',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.txt': 'text',
        '.csv': 'csv',
        '.docx': 'docx',
    }

    @classmethod
    def parse(cls, file_content: bytes, filename: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse document and extract text.

        Args:
            file_content: Raw file bytes
            filename: Original filename
            content_type: MIME type (optional, will be detected if not provided)

        Returns:
            Dictionary with:
                - text: Extracted text content
                - parser_used: Name of parser used
                - page_count: Number of pages (if applicable)
                - metadata: Additional metadata
                - requires_ocr: Whether OCR is needed

        Raises:
            ValueError: If file type is not supported
        """
        # Detect file type
        file_ext = Path(filename).suffix.lower()
        if file_ext not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {file_ext}")

        parser_type = cls.SUPPORTED_EXTENSIONS[file_ext]

        # Route to appropriate parser
        if parser_type == 'pdf':
            return PDFParser.parse(file_content, filename)
        elif parser_type == 'image':
            return ImageParser.parse(file_content, filename)
        elif parser_type == 'text':
            return TextParser.parse(file_content, filename)
        elif parser_type == 'csv':
            return CSVParser.parse(file_content, filename)
        elif parser_type == 'docx':
            return DocxParser.parse(file_content, filename)
        else:
            raise ValueError(f"No parser available for type: {parser_type}")


class PDFParser:
    """Parser for PDF documents."""

    @staticmethod
    def parse(file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract text from PDF.

        If text extraction yields minimal content, flags for OCR.
        """
        if PdfReader is None:
            raise RuntimeError("pypdf is not installed. Install with: pip install pypdf")

        try:
            pdf_file = io.BytesIO(file_content)
            reader = PdfReader(pdf_file)

            text_content = []
            page_count = len(reader.pages)

            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)

            full_text = "\n\n".join(text_content)

            # Check if OCR is needed (very little text extracted)
            requires_ocr = len(full_text.strip()) < 100 and page_count > 0

            return {
                'text': full_text,
                'parser_used': 'pypdf',
                'page_count': page_count,
                'metadata': {
                    'pdf_version': reader.pdf_header,
                    'encrypted': reader.is_encrypted,
                },
                'requires_ocr': requires_ocr
            }

        except Exception as e:
            # If PDF parsing fails, flag for OCR
            return {
                'text': '',
                'parser_used': 'pypdf',
                'page_count': 0,
                'metadata': {'error': str(e)},
                'requires_ocr': True
            }


class ImageParser:
    """Parser for image files (PNG, JPG, JPEG)."""

    @staticmethod
    def parse(file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse image file.

        Images always require OCR for text extraction.
        """
        if Image is None:
            raise RuntimeError("Pillow is not installed. Install with: pip install Pillow")

        try:
            image = Image.open(io.BytesIO(file_content))

            return {
                'text': '',  # No text without OCR
                'parser_used': 'pillow',
                'page_count': 1,
                'metadata': {
                    'format': image.format,
                    'mode': image.mode,
                    'size': image.size,
                },
                'requires_ocr': True
            }

        except Exception as e:
            raise ValueError(f"Failed to parse image: {e}")


class TextParser:
    """Parser for plain text files."""

    @staticmethod
    def parse(file_content: bytes, filename: str) -> Dict[str, Any]:
        """Extract text from plain text file."""
        try:
            # Try UTF-8 first
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback to latin-1
            try:
                text = file_content.decode('latin-1')
            except UnicodeDecodeError:
                # Last resort: ignore errors
                text = file_content.decode('utf-8', errors='ignore')

        return {
            'text': text,
            'parser_used': 'text',
            'page_count': 1,
            'metadata': {
                'encoding': 'utf-8',
                'size_bytes': len(file_content),
            },
            'requires_ocr': False
        }


class CSVParser:
    """Parser for CSV files."""

    @staticmethod
    def parse(file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse CSV and convert to readable text format.

        Converts CSV rows into formatted text with headers.
        """
        try:
            # Decode content
            text_content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            text_content = file_content.decode('latin-1', errors='ignore')

        # Parse CSV
        csv_file = io.StringIO(text_content)
        reader = csv.DictReader(csv_file)

        # Convert to formatted text
        formatted_rows = []
        row_count = 0

        for row in reader:
            row_count += 1
            row_text = []
            for key, value in row.items():
                if value:
                    row_text.append(f"{key}: {value}")

            if row_text:
                formatted_rows.append("\n".join(row_text))

        full_text = "\n\n".join(formatted_rows)

        return {
            'text': full_text,
            'parser_used': 'csv',
            'page_count': 1,
            'metadata': {
                'row_count': row_count,
                'columns': list(reader.fieldnames) if reader.fieldnames else [],
            },
            'requires_ocr': False
        }


class DocxParser:
    """Parser for DOCX (Microsoft Word) documents."""

    @staticmethod
    def parse(file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract text from DOCX file.

        Preserves paragraphs and basic structure.
        """
        if DocxDocument is None:
            raise RuntimeError("python-docx is not installed. Install with: pip install python-docx")

        try:
            docx_file = io.BytesIO(file_content)
            doc = DocxDocument(docx_file)

            # Extract paragraphs
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)

            full_text = "\n\n".join(paragraphs)

            # Try to extract metadata
            metadata = {}
            try:
                core_props = doc.core_properties
                metadata = {
                    'author': core_props.author,
                    'title': core_props.title,
                    'subject': core_props.subject,
                    'created': str(core_props.created) if core_props.created else None,
                }
            except:
                pass

            return {
                'text': full_text,
                'parser_used': 'python-docx',
                'page_count': len(doc.sections),  # Approximate
                'metadata': metadata,
                'requires_ocr': False
            }

        except Exception as e:
            raise ValueError(f"Failed to parse DOCX: {e}")


def detect_mime_type(filename: str, content: bytes) -> str:
    """
    Detect MIME type from filename and content.

    Args:
        filename: Original filename
        content: File content bytes

    Returns:
        MIME type string
    """
    # Try filename-based detection first
    mime_type, _ = mimetypes.guess_type(filename)

    if mime_type:
        return mime_type

    # Fallback: magic number detection
    if content.startswith(b'%PDF'):
        return 'application/pdf'
    elif content.startswith(b'\x89PNG'):
        return 'image/png'
    elif content.startswith(b'\xFF\xD8\xFF'):
        return 'image/jpeg'
    elif content.startswith(b'PK\x03\x04'):
        # Could be DOCX or other ZIP-based format
        if b'word/' in content[:1000]:
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        return 'application/zip'

    return 'application/octet-stream'
