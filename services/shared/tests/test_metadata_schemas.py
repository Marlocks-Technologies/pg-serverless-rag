"""Tests for metadata schema dataclasses."""

import pytest
from datetime import datetime
from shared.metadata_schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    ClassificationResult,
    DocumentMetadata,
    ChatHistoryItem,
)


def test_chat_request_creation():
    """Test creating a ChatRequest instance."""
    request = ChatRequest(
        session_id="session-123",
        message="What is failover?",
        top_k=5,
        filters={"category": ["technical-spec"]},
    )

    assert request.session_id == "session-123"
    assert request.message == "What is failover?"
    assert request.top_k == 5
    assert request.filters == {"category": ["technical-spec"]}


def test_chat_request_to_dict():
    """Test ChatRequest serialization to dictionary."""
    request = ChatRequest(
        session_id="session-123",
        message="What is failover?",
        top_k=10,
        filters={},
    )

    data = request.to_dict()

    assert isinstance(data, dict)
    assert data["sessionId"] == "session-123"
    assert data["message"] == "What is failover?"
    assert data["topK"] == 10
    assert data["filters"] == {}


def test_chat_request_from_dict():
    """Test ChatRequest deserialization from dictionary."""
    data = {
        "sessionId": "session-456",
        "message": "Test question",
        "topK": 3,
        "filters": {"category": ["legal"]},
    }

    request = ChatRequest.from_dict(data)

    assert request.session_id == "session-456"
    assert request.message == "Test question"
    assert request.top_k == 3
    assert request.filters == {"category": ["legal"]}


def test_citation_creation():
    """Test creating a Citation instance."""
    citation = Citation(
        document_id="doc-123",
        source_uri="s3://bucket/doc.pdf",
        excerpt="Relevant text excerpt",
        score=0.92,
        metadata={"category": "technical-spec"},
    )

    assert citation.document_id == "doc-123"
    assert citation.source_uri == "s3://bucket/doc.pdf"
    assert citation.score == 0.92


def test_citation_to_dict():
    """Test Citation serialization."""
    citation = Citation(
        document_id="doc-123",
        source_uri="s3://bucket/doc.pdf",
        excerpt="Text",
        score=0.85,
    )

    data = citation.to_dict()

    assert data["documentId"] == "doc-123"
    assert data["sourceUri"] == "s3://bucket/doc.pdf"
    assert data["excerpt"] == "Text"
    assert data["score"] == 0.85


def test_chat_response_with_citations():
    """Test ChatResponse with multiple citations."""
    citations = [
        Citation(
            document_id="doc-1",
            source_uri="s3://bucket/doc1.pdf",
            excerpt="Excerpt 1",
            score=0.95,
        ),
        Citation(
            document_id="doc-2",
            source_uri="s3://bucket/doc2.pdf",
            excerpt="Excerpt 2",
            score=0.88,
        ),
    ]

    response = ChatResponse(
        session_id="session-123",
        answer="The answer is...",
        citations=citations,
        request_id="req-xyz",
    )

    assert response.session_id == "session-123"
    assert response.answer == "The answer is..."
    assert len(response.citations) == 2
    assert response.request_id == "req-xyz"


def test_chat_response_to_dict():
    """Test ChatResponse serialization with nested citations."""
    citations = [
        Citation(
            document_id="doc-1",
            source_uri="s3://bucket/doc1.pdf",
            excerpt="Excerpt",
            score=0.9,
        )
    ]

    response = ChatResponse(
        session_id="session-123",
        answer="Answer text",
        citations=citations,
        request_id="req-abc",
    )

    data = response.to_dict()

    assert data["sessionId"] == "session-123"
    assert data["answer"] == "Answer text"
    assert len(data["citations"]) == 1
    assert data["citations"][0]["documentId"] == "doc-1"
    assert data["requestId"] == "req-abc"


def test_classification_result_round_trip():
    """Test ClassificationResult serialization and deserialization."""
    original = ClassificationResult(
        primary_tag="technical-spec",
        secondary_tags=["architecture", "API"],
        confidence=0.92,
        grouping_reason="Contains system architecture",
    )

    data = original.to_dict()
    restored = ClassificationResult.from_dict(data)

    assert restored.primary_tag == original.primary_tag
    assert restored.secondary_tags == original.secondary_tags
    assert restored.confidence == original.confidence
    assert restored.grouping_reason == original.grouping_reason


def test_document_metadata_complex():
    """Test DocumentMetadata with nested structures."""
    metadata = DocumentMetadata(
        document_id="uuid-12345",
        source={
            "bucket": "ingestion-bucket",
            "key": "uploads/file.pdf",
            "filename": "file.pdf",
            "contentType": "application/pdf",
        },
        classification={
            "primaryTag": "invoice",
            "secondaryTags": ["payment"],
            "confidence": 0.95,
        },
        grouping={"prefix": "invoice", "reason": "Contains invoice number"},
        processing={
            "timestamp": "2026-03-24T12:00:00.000Z",
            "parser": "pdf",
            "ocrUsed": False,
        },
    )

    assert metadata.document_id == "uuid-12345"
    assert metadata.source["bucket"] == "ingestion-bucket"
    assert metadata.classification["primaryTag"] == "invoice"


def test_document_metadata_round_trip():
    """Test DocumentMetadata full serialization round trip."""
    original_data = {
        "documentId": "uuid-abc",
        "source": {
            "bucket": "test-bucket",
            "key": "test.pdf",
            "filename": "test.pdf",
            "contentType": "application/pdf",
        },
        "classification": {
            "primaryTag": "legal",
            "secondaryTags": [],
            "confidence": 0.88,
        },
        "grouping": {"prefix": "legal", "reason": "Legal contract"},
        "processing": {
            "timestamp": "2026-03-24T10:00:00.000Z",
            "parser": "pdf",
            "ocrUsed": False,
        },
    }

    metadata = DocumentMetadata.from_dict(original_data)
    restored_data = metadata.to_dict()

    assert restored_data["documentId"] == original_data["documentId"]
    assert restored_data["source"] == original_data["source"]
    assert restored_data["classification"] == original_data["classification"]


def test_chat_history_item():
    """Test ChatHistoryItem creation and serialization."""
    item = ChatHistoryItem(
        session_id="session-123",
        timestamp="2026-03-24T12:00:00.000Z",
        role="user",
        message="What is the policy?",
        citations=None,
        metadata={"request_id": "req-123"},
    )

    assert item.session_id == "session-123"
    assert item.role == "user"
    assert item.message == "What is the policy?"

    data = item.to_dict()
    assert data["sessionId"] == "session-123"
    assert data["role"] == "user"
