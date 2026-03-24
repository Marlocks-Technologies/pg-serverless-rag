"""
Text processing utilities for normalization and chunking.
"""

import re
import hashlib
from typing import List, Dict, Any
from datetime import datetime


def normalize_text(text: str, source_metadata: Dict[str, Any] = None) -> str:
    """
    Normalize extracted text into canonical form.

    Args:
        text: Raw extracted text
        source_metadata: Optional metadata to attach as header

    Returns:
        Normalized text with consistent formatting
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace("\x00", "")

    # Remove other control characters except newline, tab, carriage return
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse excessive whitespace (preserve paragraphs)
    # Replace multiple spaces with single space
    text = re.sub(r" +", " ", text)

    # Replace more than 2 consecutive newlines with 2 newlines (paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Optionally prepend metadata header
    if source_metadata:
        header = _build_metadata_header(source_metadata)
        text = f"{header}\n\n{text}"

    return text


def _build_metadata_header(metadata: Dict[str, Any]) -> str:
    """Build a metadata header for the document."""
    header_parts = []

    if 'filename' in metadata:
        header_parts.append(f"Source: {metadata['filename']}")

    if 'upload_timestamp' in metadata:
        header_parts.append(f"Uploaded: {metadata['upload_timestamp']}")

    if 'content_type' in metadata:
        header_parts.append(f"Type: {metadata['content_type']}")

    if header_parts:
        return "=== Document Metadata ===\n" + "\n".join(header_parts) + "\n=== End Metadata ==="

    return ""


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap_percentage: float = 0.15,
    preserve_sentences: bool = True
) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks for embedding.

    Args:
        text: Full document text
        chunk_size: Target size in tokens (approximated by words)
        overlap_percentage: Percentage of overlap between chunks (0.0 to 1.0)
        preserve_sentences: Try to break on sentence boundaries

    Returns:
        List of chunks, each containing:
            - text: Chunk text
            - token_count: Approximate token count
            - chunk_index: Index in sequence
            - start_char: Starting character position
            - end_char: Ending character position
    """
    if not text:
        return []

    # Simple word-based chunking (production: use tiktoken for accurate token counts)
    words = text.split()

    if not words:
        return []

    words_per_chunk = chunk_size
    overlap_words = int(words_per_chunk * overlap_percentage)

    chunks = []
    chunk_index = 0
    start_word = 0

    while start_word < len(words):
        end_word = min(start_word + words_per_chunk, len(words))

        # Try to break on sentence boundary if requested
        if preserve_sentences and end_word < len(words):
            # Look for sentence-ending punctuation in the last 20% of chunk
            search_start = start_word + int(words_per_chunk * 0.8)
            for i in range(end_word - 1, search_start, -1):
                if i < len(words) and words[i].endswith(('.', '!', '?')):
                    end_word = i + 1
                    break

        chunk_words = words[start_word:end_word]
        chunk_text = ' '.join(chunk_words)

        # Calculate character positions
        # (Approximate - in production, track precise positions)
        chars_before = len(' '.join(words[:start_word]))
        chars_in_chunk = len(chunk_text)

        chunks.append({
            'text': chunk_text,
            'token_count': len(chunk_words),  # Approximate
            'chunk_index': chunk_index,
            'start_char': chars_before,
            'end_char': chars_before + chars_in_chunk,
            'word_count': len(chunk_words)
        })

        chunk_index += 1

        # Move to next chunk with overlap
        start_word = end_word - overlap_words

        # Prevent infinite loop
        if start_word >= end_word:
            break

    return chunks


def extract_classification_snippet(text: str, max_length: int = 2000) -> str:
    """
    Extract a snippet of text for classification.

    Takes the beginning and end of the document to capture key information.

    Args:
        text: Full document text
        max_length: Maximum snippet length in characters

    Returns:
        Text snippet suitable for classification
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    # Take first 60% and last 40% of max_length
    first_part_len = int(max_length * 0.6)
    last_part_len = int(max_length * 0.4)

    first_part = text[:first_part_len]
    last_part = text[-last_part_len:]

    # Find good break points (sentence boundaries)
    if '.' in first_part[-200:]:
        break_point = first_part.rfind('.', -200)
        if break_point > 0:
            first_part = first_part[:break_point + 1]

    if '.' in last_part[:200]:
        break_point = last_part.find('.', 0, 200)
        if break_point > 0:
            last_part = last_part[break_point + 1:]

    snippet = first_part + "\n\n[... middle section omitted ...]\n\n" + last_part

    return snippet.strip()


def compute_text_hash(text: str) -> str:
    """
    Compute SHA-256 hash of text for deduplication.

    Args:
        text: Text content

    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.

    Simple approximation: 1 token ~= 0.75 words for English text.

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    word_count = len(text.split())
    return int(word_count * 1.33)  # ~0.75 words per token


def truncate_text(text: str, max_tokens: int) -> str:
    """
    Truncate text to approximate token limit.

    Args:
        text: Input text
        max_tokens: Maximum token count

    Returns:
        Truncated text
    """
    words = text.split()
    max_words = int(max_tokens * 0.75)

    if len(words) <= max_words:
        return text

    truncated_words = words[:max_words]
    return ' '.join(truncated_words) + "..."


def split_into_paragraphs(text: str) -> List[str]:
    """
    Split text into paragraphs.

    Args:
        text: Input text

    Returns:
        List of paragraph strings
    """
    # Split on double newlines
    paragraphs = re.split(r'\n\s*\n', text)

    # Filter out empty paragraphs
    return [p.strip() for p in paragraphs if p.strip()]


def preserve_table_structure(text: str) -> str:
    """
    Detect and preserve table-like structures in text.

    Args:
        text: Input text that may contain tables

    Returns:
        Text with tables formatted for readability
    """
    lines = text.split('\n')
    formatted_lines = []

    for line in lines:
        # Detect potential table rows (multiple tab or pipe separators)
        if '\t' in line or '|' in line:
            # Format as table row
            if '\t' in line:
                cells = line.split('\t')
            else:
                cells = [c.strip() for c in line.split('|') if c.strip()]

            if cells:
                formatted_line = ' | '.join(cells)
                formatted_lines.append(formatted_line)
        else:
            formatted_lines.append(line)

    return '\n'.join(formatted_lines)


def extract_metadata_from_text(text: str) -> Dict[str, str]:
    """
    Extract potential metadata from document text.

    Looks for patterns like "Title:", "Author:", "Date:", etc.

    Args:
        text: Document text

    Returns:
        Dictionary of extracted metadata
    """
    metadata = {}

    # Common metadata patterns
    patterns = {
        'title': r'(?:Title|Subject|Regarding):\s*(.+?)(?:\n|$)',
        'author': r'(?:Author|By|From):\s*(.+?)(?:\n|$)',
        'date': r'(?:Date|Created|Published):\s*(.+?)(?:\n|$)',
        'version': r'(?:Version|Rev|Revision):\s*(.+?)(?:\n|$)',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text[:1000], re.IGNORECASE)
        if match:
            metadata[key] = match.group(1).strip()

    return metadata
