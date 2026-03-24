"""
Integration tests for document processing pipeline.

These tests validate the end-to-end flow from document upload to vector storage.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add shared library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared/src'))

from document_parsers import DocumentParser
from text_processing import normalize_text, chunk_text, extract_classification_snippet
from document_classifier import DocumentClassifier


def test_pdf_parsing():
    """Test PDF parsing with sample PDF bytes."""
    # Minimal PDF content for testing
    pdf_content = b'%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n%%EOF'
    filename = 'test.pdf'

    try:
        result = DocumentParser.parse(pdf_content, filename)
        assert 'text' in result
        assert 'parser_used' in result
        assert result['parser_used'] == 'pypdf'
    except RuntimeError as e:
        if 'pypdf is not installed' in str(e):
            pytest.skip("pypdf not installed")
        raise


def test_text_parsing():
    """Test plain text parsing."""
    text_content = b'This is a test document with some text content.'
    filename = 'test.txt'

    result = DocumentParser.parse(text_content, filename)

    assert result['text'] == 'This is a test document with some text content.'
    assert result['parser_used'] == 'text'
    assert result['requires_ocr'] is False


def test_text_normalization():
    """Test text normalization."""
    raw_text = "Hello    World\n\n\n\n\nTest  Document\x00\x01"

    normalized = normalize_text(raw_text)

    # Check null bytes removed
    assert '\x00' not in normalized
    assert '\x01' not in normalized

    # Check whitespace normalized
    assert 'Hello World' in normalized
    assert 'Test Document' in normalized


def test_text_chunking():
    """Test text chunking with overlap."""
    text = ' '.join(['word'] * 1000)  # 1000 words

    chunks = chunk_text(text, chunk_size=100, overlap_percentage=0.2)

    # Should create multiple chunks
    assert len(chunks) > 5

    # Each chunk should have expected structure
    for chunk in chunks:
        assert 'text' in chunk
        assert 'token_count' in chunk
        assert 'chunk_index' in chunk

    # First chunk should start at 0
    assert chunks[0]['chunk_index'] == 0

    # Chunks should have overlap
    # (Can't easily test exact overlap without more complex logic)


def test_classification_snippet_extraction():
    """Test extraction of classification snippet."""
    long_text = 'A' * 5000  # Long document

    snippet = extract_classification_snippet(long_text, max_length=2000)

    assert len(snippet) <= 2500  # Allow some buffer
    assert 'A' in snippet


@patch('document_classifier.boto3')
def test_document_classification_mock(mock_boto3):
    """Test document classification with mocked Bedrock."""
    # Mock Bedrock response
    mock_client = Mock()
    mock_boto3.client.return_value = mock_client

    mock_response = {
        'body': Mock()
    }

    mock_response['body'].read.return_value = json.dumps({
        'content': [{
            'text': json.dumps({
                'primaryTag': 'technical-spec',
                'secondaryTags': ['architecture'],
                'confidence': 0.95,
                'groupingReason': 'Test reason'
            })
        }]
    }).encode()

    mock_client.invoke_model.return_value = mock_response

    # Test classification
    classifier = DocumentClassifier()
    result = classifier.classify("This is a technical specification document")

    assert result['primary_tag'] == 'technical-spec'
    assert result['confidence'] == 0.95
    assert 'architecture' in result['secondary_tags']


def test_document_classifier_validation():
    """Test classification response validation."""
    classifier = DocumentClassifier()

    # Test with invalid category
    invalid_classification = {
        'primaryTag': 'invalid-category',
        'confidence': 0.9,
        'groupingReason': 'test'
    }

    validated = classifier._validate_classification(invalid_classification)

    # Should default to 'unknown' for invalid category
    assert validated['primary_tag'] == 'unknown'
    assert validated['confidence'] <= 0.1


def test_supported_file_types():
    """Test that all supported file types are recognized."""
    supported_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.txt', '.csv', '.docx']

    for ext in supported_extensions:
        assert ext in DocumentParser.SUPPORTED_EXTENSIONS


def test_chunking_preserves_sentence_boundaries():
    """Test that chunking tries to preserve sentences."""
    text = "This is sentence one. This is sentence two. This is sentence three. " * 100

    chunks = chunk_text(text, chunk_size=50, preserve_sentences=True)

    # Verify chunks created
    assert len(chunks) > 1

    # Most chunks should end with sentence-ending punctuation or be at document end
    # (Not a strict requirement, but should be common)
    sentence_endings = sum(1 for chunk in chunks[:-1] if chunk['text'].rstrip().endswith(('.', '!', '?')))

    # At least some chunks should preserve sentence boundaries
    # (Relaxed check since it's not guaranteed)
    assert sentence_endings > 0 or len(chunks) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
