"""Data models (dataclasses / TypedDicts) for the RAG Platform.

All classes provide to_dict() / from_dict() for serialisation round-trips.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# ─── DocumentMetadata ─────────────────────────────────────────────────────────

@dataclass
class DocumentMetadata:
    """Metadata manifest stored alongside a processed document in S3."""

    document_id: str
    source_filename: str
    source_bucket: str
    source_key: str
    staging_key: str
    content_type: str                   # MIME type of the original file
    primary_tag: str                    # Classification primary tag
    secondary_tags: list[str]           # Classification secondary tags
    confidence: float                   # Classification confidence 0.0-1.0
    grouping_reason: str                # Human-readable grouping rationale
    extraction_timestamp: str           # ISO-8601 UTC timestamp
    checksum_sha256: str                # SHA-256 of the original file bytes
    page_count: Optional[int] = None   # PDF page count (if applicable)
    word_count: Optional[int] = None
    language: Optional[str] = None
    custom: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentMetadata":
        return cls(
            document_id=data["document_id"],
            source_filename=data["source_filename"],
            source_bucket=data["source_bucket"],
            source_key=data["source_key"],
            staging_key=data["staging_key"],
            content_type=data["content_type"],
            primary_tag=data["primary_tag"],
            secondary_tags=data.get("secondary_tags", []),
            confidence=float(data.get("confidence", 0.0)),
            grouping_reason=data.get("grouping_reason", ""),
            extraction_timestamp=data["extraction_timestamp"],
            checksum_sha256=data["checksum_sha256"],
            page_count=data.get("page_count"),
            word_count=data.get("word_count"),
            language=data.get("language"),
            custom=data.get("custom", {}),
        )


# ─── ClassificationResult ─────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """Output from the document classifier (Claude Haiku)."""

    primary_tag: str
    secondary_tags: list[str]
    confidence: float
    grouping_reason: str

    VALID_PRIMARY_TAGS = frozenset(
        {"invoice", "hr", "technical-spec", "legal", "finance", "operations", "unknown"}
    )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ClassificationResult":
        return cls(
            primary_tag=data.get("primaryTag", data.get("primary_tag", "unknown")),
            secondary_tags=data.get("secondaryTags", data.get("secondary_tags", [])),
            confidence=float(data.get("confidence", 0.0)),
            grouping_reason=data.get("groupingReason", data.get("grouping_reason", "")),
        )


# ─── ChatHistoryItem ──────────────────────────────────────────────────────────

@dataclass
class ChatHistoryItem:
    """A single turn in a chat session."""

    session_id: str
    timestamp: str          # ISO-8601 UTC
    role: str               # "user" or "assistant"
    message: str
    citations: list["Citation"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "role": self.role,
            "message": self.message,
            "citations": [c.to_dict() for c in self.citations],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatHistoryItem":
        citations = [Citation.from_dict(c) for c in data.get("citations", [])]
        return cls(
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            role=data["role"],
            message=data["message"],
            citations=citations,
            metadata=data.get("metadata", {}),
        )


# ─── Citation ─────────────────────────────────────────────────────────────────

@dataclass
class Citation:
    """A source citation included in an assistant response."""

    document_id: str
    source_filename: str
    excerpt: str
    page_number: Optional[int] = None
    score: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Citation":
        return cls(
            document_id=data["document_id"],
            source_filename=data["source_filename"],
            excerpt=data.get("excerpt", ""),
            page_number=data.get("page_number"),
            score=data.get("score"),
        )


# ─── ChatRequest ──────────────────────────────────────────────────────────────

@dataclass
class ChatRequest:
    """Incoming POST /chat/query request body."""

    query: str
    session_id: str
    top_k: int = 5
    filters: Optional[dict] = None
    stream: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChatRequest":
        return cls(
            query=data["query"],
            session_id=data.get("session_id", str(uuid.uuid4())),
            top_k=int(data.get("top_k", 5)),
            filters=data.get("filters"),
            stream=bool(data.get("stream", False)),
        )


# ─── ChatResponse ─────────────────────────────────────────────────────────────

@dataclass
class ChatResponse:
    """Response body for POST /chat/query."""

    session_id: str
    answer: str
    citations: list[Citation]
    model_id: str
    usage: dict[str, int] = field(default_factory=dict)   # input/output token counts
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "model_id": self.model_id,
            "usage": self.usage,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatResponse":
        citations = [Citation.from_dict(c) for c in data.get("citations", [])]
        return cls(
            session_id=data["session_id"],
            answer=data["answer"],
            citations=citations,
            model_id=data["model_id"],
            usage=data.get("usage", {}),
            metadata=data.get("metadata", {}),
        )
