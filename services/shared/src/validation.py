"""Input validation and sanitization utilities."""

import re
from typing import Any, Dict, Optional
from .metadata_schemas import ChatRequest, ChatResponse, ClassificationResult, DocumentMetadata


def validate_chat_request(data: Dict[str, Any]) -> ChatRequest:
    """
    Validate chat request data against the expected schema.

    Args:
        data: Raw request data dictionary

    Returns:
        Validated ChatRequest object

    Raises:
        ValueError: If validation fails with descriptive message
    """
    if not isinstance(data, dict):
        raise ValueError("Request must be a JSON object")

    # Required fields
    if "sessionId" not in data:
        raise ValueError("Missing required field: sessionId")
    if "message" not in data:
        raise ValueError("Missing required field: message")

    session_id = data["sessionId"]
    message = data["message"]

    # Validate types
    if not isinstance(session_id, str):
        raise ValueError("sessionId must be a string")
    if not isinstance(message, str):
        raise ValueError("message must be a string")

    # Validate lengths
    if not session_id or len(session_id) > 256:
        raise ValueError("sessionId must be between 1 and 256 characters")
    if not message or len(message) > 10000:
        raise ValueError("message must be between 1 and 10000 characters")

    # Optional fields
    top_k = data.get("topK", 5)
    if not isinstance(top_k, int) or top_k < 1 or top_k > 100:
        raise ValueError("topK must be an integer between 1 and 100")

    filters = data.get("filters")
    if filters is not None and not isinstance(filters, dict):
        raise ValueError("filters must be an object")

    return ChatRequest(
        session_id=session_id,
        message=sanitize_text(message),
        top_k=top_k,
        filters=filters or {}
    )


def validate_classification_response(data: Dict[str, Any]) -> ClassificationResult:
    """
    Validate classification response from LLM against expected schema.

    Args:
        data: Raw classification result from model

    Returns:
        Validated ClassificationResult object

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(data, dict):
        raise ValueError("Classification response must be a JSON object")

    # Required fields
    required = ["primaryTag", "confidence", "groupingReason"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    primary_tag = data["primaryTag"]
    confidence = data["confidence"]
    grouping_reason = data["groupingReason"]
    secondary_tags = data.get("secondaryTags", [])

    # Validate types
    if not isinstance(primary_tag, str):
        raise ValueError("primaryTag must be a string")
    if not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be a number")
    if not isinstance(grouping_reason, str):
        raise ValueError("groupingReason must be a string")
    if not isinstance(secondary_tags, list):
        raise ValueError("secondaryTags must be an array")

    # Validate ranges
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")

    # Validate allowed categories
    allowed_categories = {
        "invoice", "hr", "technical-spec", "legal",
        "finance", "operations", "unknown"
    }
    if primary_tag not in allowed_categories:
        raise ValueError(
            f"primaryTag must be one of: {', '.join(sorted(allowed_categories))}"
        )

    for tag in secondary_tags:
        if not isinstance(tag, str):
            raise ValueError("All secondary tags must be strings")

    return ClassificationResult(
        primary_tag=primary_tag,
        secondary_tags=secondary_tags,
        confidence=float(confidence),
        grouping_reason=grouping_reason
    )


def validate_document_metadata(data: Dict[str, Any]) -> DocumentMetadata:
    """
    Validate document metadata against expected schema.

    Args:
        data: Raw metadata dictionary

    Returns:
        Validated DocumentMetadata object

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(data, dict):
        raise ValueError("Document metadata must be a JSON object")

    required = ["documentId", "source", "classification", "grouping", "processing"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    return DocumentMetadata.from_dict(data)


def sanitize_text(text: str) -> str:
    """
    Remove null bytes, control characters, and normalize whitespace.

    Args:
        text: Raw text input

    Returns:
        Sanitized text safe for processing
    """
    if not isinstance(text, str):
        return ""

    # Remove null bytes
    text = text.replace("\x00", "")

    # Remove other control characters except newline, tab, carriage return
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse excessive whitespace (but preserve single newlines)
    # Replace multiple spaces with single space
    text = re.sub(r" +", " ", text)

    # Replace more than 2 consecutive newlines with 2 newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove potentially dangerous characters.

    Args:
        filename: Original filename

    Returns:
        Safe filename suitable for storage
    """
    if not filename:
        return "unnamed"

    # Remove path separators and null bytes
    filename = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")

    # Remove other problematic characters
    filename = re.sub(r'[<>:"|?*]', "_", filename)

    # Collapse multiple underscores
    filename = re.sub(r"_+", "_", filename)

    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        if ext:
            filename = name[:250] + "." + ext
        else:
            filename = filename[:255]

    return filename or "unnamed"
