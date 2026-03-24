"""Tests for input validation and sanitization."""

import pytest
from shared.validation import (
    validate_chat_request,
    validate_classification_response,
    validate_document_metadata,
    sanitize_text,
    sanitize_filename,
)
from shared.metadata_schemas import ChatRequest, ClassificationResult, DocumentMetadata


def test_validate_chat_request_valid():
    """Test validation of a valid chat request."""
    data = {
        "sessionId": "session-123",
        "message": "What is the policy?",
        "topK": 5,
        "filters": {"category": ["legal"]},
    }

    request = validate_chat_request(data)

    assert isinstance(request, ChatRequest)
    assert request.session_id == "session-123"
    assert request.message == "What is the policy?"
    assert request.top_k == 5


def test_validate_chat_request_missing_session_id():
    """Test validation fails when sessionId is missing."""
    data = {
        "message": "What is the policy?",
    }

    with pytest.raises(ValueError) as exc_info:
        validate_chat_request(data)

    assert "sessionId" in str(exc_info.value)


def test_validate_chat_request_missing_message():
    """Test validation fails when message is missing."""
    data = {
        "sessionId": "session-123",
    }

    with pytest.raises(ValueError) as exc_info:
        validate_chat_request(data)

    assert "message" in str(exc_info.value)


def test_validate_chat_request_invalid_top_k():
    """Test validation fails for invalid topK values."""
    data = {
        "sessionId": "session-123",
        "message": "Test",
        "topK": 0,  # Too small
    }

    with pytest.raises(ValueError) as exc_info:
        validate_chat_request(data)

    assert "topK" in str(exc_info.value)


def test_validate_chat_request_sanitizes_message():
    """Test that message text is sanitized."""
    data = {
        "sessionId": "session-123",
        "message": "Test\x00message\n\n\n\nwith nulls",
    }

    request = validate_chat_request(data)

    # Null byte should be removed, excessive newlines collapsed
    assert "\x00" not in request.message
    assert request.message == "Test message\n\nwith nulls"


def test_validate_classification_response_valid():
    """Test validation of a valid classification response."""
    data = {
        "primaryTag": "technical-spec",
        "secondaryTags": ["architecture"],
        "confidence": 0.92,
        "groupingReason": "Contains system architecture",
    }

    result = validate_classification_response(data)

    assert isinstance(result, ClassificationResult)
    assert result.primary_tag == "technical-spec"
    assert result.confidence == 0.92


def test_validate_classification_response_invalid_category():
    """Test validation fails for invalid category."""
    data = {
        "primaryTag": "invalid-category",
        "confidence": 0.9,
        "groupingReason": "Test",
    }

    with pytest.raises(ValueError) as exc_info:
        validate_classification_response(data)

    assert "primaryTag" in str(exc_info.value)


def test_validate_classification_response_invalid_confidence():
    """Test validation fails for confidence out of range."""
    data = {
        "primaryTag": "invoice",
        "confidence": 1.5,  # > 1.0
        "groupingReason": "Test",
    }

    with pytest.raises(ValueError) as exc_info:
        validate_classification_response(data)

    assert "confidence" in str(exc_info.value)


def test_validate_classification_response_missing_field():
    """Test validation fails when required field is missing."""
    data = {
        "primaryTag": "invoice",
        "confidence": 0.9,
        # Missing groupingReason
    }

    with pytest.raises(ValueError) as exc_info:
        validate_classification_response(data)

    assert "groupingReason" in str(exc_info.value)


def test_sanitize_text_removes_null_bytes():
    """Test that sanitize_text removes null bytes."""
    text = "Hello\x00World"
    sanitized = sanitize_text(text)
    assert "\x00" not in sanitized
    assert sanitized == "Hello World"


def test_sanitize_text_removes_control_chars():
    """Test that control characters are removed."""
    text = "Hello\x01\x02\x03World"
    sanitized = sanitize_text(text)
    assert "\x01" not in sanitized
    assert "\x02" not in sanitized
    assert sanitized == "Hello World"


def test_sanitize_text_preserves_newlines_and_tabs():
    """Test that newlines and tabs are preserved."""
    text = "Hello\nWorld\tTest"
    sanitized = sanitize_text(text)
    assert "\n" in sanitized
    assert "\t" in sanitized


def test_sanitize_text_collapses_whitespace():
    """Test that excessive whitespace is collapsed."""
    text = "Hello    World"
    sanitized = sanitize_text(text)
    assert sanitized == "Hello World"


def test_sanitize_text_collapses_newlines():
    """Test that excessive newlines are collapsed."""
    text = "Hello\n\n\n\n\nWorld"
    sanitized = sanitize_text(text)
    assert sanitized == "Hello\n\nWorld"


def test_sanitize_text_strips_leading_trailing():
    """Test that leading and trailing whitespace is stripped."""
    text = "  Hello World  \n"
    sanitized = sanitize_text(text)
    assert sanitized == "Hello World"


def test_sanitize_text_empty_string():
    """Test sanitizing empty string."""
    assert sanitize_text("") == ""


def test_sanitize_text_non_string():
    """Test sanitizing non-string returns empty string."""
    assert sanitize_text(None) == ""
    assert sanitize_text(123) == ""


def test_sanitize_filename_removes_path_separators():
    """Test that path separators are replaced."""
    filename = "path/to/file.txt"
    sanitized = sanitize_filename(filename)
    assert "/" not in sanitized
    assert sanitized == "path_to_file.txt"


def test_sanitize_filename_removes_dangerous_chars():
    """Test that dangerous characters are removed."""
    filename = 'file<>:"|?*.txt'
    sanitized = sanitize_filename(filename)
    assert all(c not in sanitized for c in '<>:"|?*')


def test_sanitize_filename_collapses_underscores():
    """Test that multiple underscores are collapsed."""
    filename = "file___name.txt"
    sanitized = sanitize_filename(filename)
    assert "___" not in sanitized


def test_sanitize_filename_limits_length():
    """Test that filenames are truncated to 255 chars."""
    filename = "a" * 300 + ".txt"
    sanitized = sanitize_filename(filename)
    assert len(sanitized) <= 255
    assert sanitized.endswith(".txt")


def test_sanitize_filename_empty():
    """Test sanitizing empty filename."""
    assert sanitize_filename("") == "unnamed"
    assert sanitize_filename(None) == "unnamed"


def test_validate_document_metadata_valid():
    """Test validation of valid document metadata."""
    data = {
        "documentId": "uuid-123",
        "source": {
            "bucket": "test-bucket",
            "key": "test.pdf",
            "filename": "test.pdf",
            "contentType": "application/pdf",
        },
        "classification": {
            "primaryTag": "invoice",
            "confidence": 0.9,
        },
        "grouping": {"prefix": "invoice", "reason": "Invoice document"},
        "processing": {
            "timestamp": "2026-03-24T10:00:00.000Z",
            "parser": "pdf",
        },
    }

    metadata = validate_document_metadata(data)

    assert isinstance(metadata, DocumentMetadata)
    assert metadata.document_id == "uuid-123"


def test_validate_document_metadata_missing_field():
    """Test validation fails when required field is missing."""
    data = {
        "documentId": "uuid-123",
        # Missing source
        "classification": {
            "primaryTag": "invoice",
            "confidence": 0.9,
        },
        "grouping": {"prefix": "invoice", "reason": "Test"},
        "processing": {
            "timestamp": "2026-03-24T10:00:00.000Z",
            "parser": "pdf",
        },
    }

    with pytest.raises(ValueError) as exc_info:
        validate_document_metadata(data)

    assert "source" in str(exc_info.value)


def test_validate_chat_request_not_dict():
    """Test validation fails when input is not a dictionary."""
    with pytest.raises(ValueError) as exc_info:
        validate_chat_request("not a dict")

    assert "JSON object" in str(exc_info.value)
