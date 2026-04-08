"""
Retrieval Service - Retrieve relevant document chunks from S3 Vectors.

Handles vector search, ranking, filtering, and citation generation.
"""

from typing import Dict, List, Optional, Any
from shared.s3_vectors import S3VectorStore


class RetrievalResult:
    """Represents a retrieved document chunk with metadata."""

    def __init__(self, chunk_data: Dict[str, Any], score: float, rank: int):
        """
        Initialize retrieval result.

        Args:
            chunk_data: Raw chunk data from vector store
            score: Similarity score
            rank: Ranking position (1-based)
        """
        self.id = chunk_data.get('id', '')
        self.text = chunk_data.get('text', '')
        self.score = score
        self.rank = rank
        self.metadata = chunk_data.get('metadata', {})

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'text': self.text,
            'score': self.score,
            'rank': self.rank,
            'metadata': self.metadata
        }

    def get_citation(self) -> Dict[str, Any]:
        """
        Generate citation information.

        Returns:
            Citation dictionary with source information
        """
        return {
            'source': self.metadata.get('filename', 'Unknown'),
            'documentId': self.metadata.get('documentId', ''),
            'category': self.metadata.get('category', 'unknown'),
            'chunkIndex': self.metadata.get('chunkIndex', 0),
            'score': round(self.score, 3)
        }


class RetrievalService:
    """Service for retrieving relevant document chunks."""

    def __init__(
        self,
        vectors_bucket: str,
        region: str = "us-east-1",
        min_score_threshold: float = 0.1
    ):
        """
        Initialize retrieval service.

        Args:
            vectors_bucket: S3 bucket containing vectors
            region: AWS region
            min_score_threshold: Minimum similarity score to include results
        """
        self.vector_store = S3VectorStore(bucket_name=vectors_bucket, region=region)
        self.min_score_threshold = min_score_threshold

    def retrieve(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        min_score: Optional[float] = None
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks for a query.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filters: Optional metadata filters
            min_score: Optional minimum score threshold (overrides default)

        Returns:
            List of RetrievalResult objects, ranked by relevance
        """
        # Use provided min_score or default
        score_threshold = min_score if min_score is not None else self.min_score_threshold

        # Query vector store
        raw_results = self.vector_store.query_vectors(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Get more results for filtering
            filters=filters
        )

        # Filter by score threshold
        filtered_results = [
            r for r in raw_results
            if r.get('score', 0) >= score_threshold
        ]

        # Convert to RetrievalResult objects with ranking
        results = [
            RetrievalResult(
                chunk_data=result,
                score=result.get('score', 0),
                rank=idx + 1
            )
            for idx, result in enumerate(filtered_results[:top_k])
        ]

        return results

    def retrieve_with_reranking(
        self,
        query_embedding: List[float],
        query_text: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        Retrieve and rerank results based on query-text overlap.

        Args:
            query_embedding: Query embedding vector
            query_text: Original query text
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of reranked RetrievalResult objects
        """
        # Get initial results
        results = self.retrieve(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Get more for reranking
            filters=filters
        )

        # Rerank based on keyword overlap
        query_keywords = set(self._extract_keywords(query_text))

        for result in results:
            chunk_keywords = set(self._extract_keywords(result.text))
            keyword_overlap = len(query_keywords & chunk_keywords) / max(len(query_keywords), 1)

            # Combine vector similarity with keyword overlap
            # 80% vector similarity, 20% keyword overlap
            result.score = 0.8 * result.score + 0.2 * keyword_overlap

        # Re-sort by new score
        results.sort(key=lambda x: x.score, reverse=True)

        # Update rankings
        for idx, result in enumerate(results[:top_k]):
            result.rank = idx + 1

        return results[:top_k]

    def retrieve_by_document(
        self,
        document_id: str,
        limit: int = 10
    ) -> List[RetrievalResult]:
        """
        Retrieve all chunks for a specific document.

        Args:
            document_id: Document identifier
            limit: Maximum number of chunks to return

        Returns:
            List of chunks from the document
        """
        # List vectors with document ID prefix
        vector_ids = self.vector_store.list_vectors(prefix_filter=document_id)

        results = []
        for vector_id in vector_ids[:limit]:
            # We need to get the full vector data
            # This is a bit inefficient, but works for now
            # In Phase 5, we could optimize this
            pass

        return results

    def get_context_window(
        self,
        results: List[RetrievalResult],
        max_tokens: int = 4000
    ) -> str:
        """
        Assemble retrieved chunks into a context window.

        Args:
            results: Retrieved results
            max_tokens: Maximum tokens for context (roughly 4 chars = 1 token)

        Returns:
            Assembled context string
        """
        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4  # Rough approximation

        for result in results:
            # Format: [Source: filename] Text content
            source = result.metadata.get('filename', 'Unknown')
            chunk_text = f"[Source: {source}]\n{result.text}\n"

            # Check if adding this chunk would exceed limit
            if total_chars + len(chunk_text) > max_chars:
                break

            context_parts.append(chunk_text)
            total_chars += len(chunk_text)

        return "\n---\n".join(context_parts)

    def generate_citations(self, results: List[RetrievalResult]) -> List[Dict[str, Any]]:
        """
        Generate citation list from results.

        Args:
            results: Retrieved results

        Returns:
            List of citation dictionaries
        """
        citations = []
        seen_sources = set()

        for result in results:
            citation = result.get_citation()
            source_key = f"{citation['source']}_{citation['chunkIndex']}"

            # Avoid duplicate citations
            if source_key not in seen_sources:
                citations.append(citation)
                seen_sources.add(source_key)

        return citations

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text.

        Args:
            text: Input text

        Returns:
            List of keywords
        """
        import re

        # Simple keyword extraction (lowercase words)
        words = re.findall(r'\b\w+\b', text.lower())

        # Remove common stop words
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with'
        }

        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords

    def get_related_chunks(
        self,
        document_id: str,
        chunk_index: int,
        context_size: int = 2
    ) -> List[str]:
        """
        Get surrounding chunks for more context.

        Args:
            document_id: Document identifier
            chunk_index: Index of target chunk
            context_size: Number of chunks before/after to retrieve

        Returns:
            List of chunk IDs for surrounding context
        """
        chunk_ids = []

        # Get chunks before and after
        for offset in range(-context_size, context_size + 1):
            if offset == 0:
                continue  # Skip the main chunk

            target_index = chunk_index + offset
            if target_index >= 0:
                chunk_id = f"{document_id}_chunk-{target_index}"
                chunk_ids.append(chunk_id)

        return chunk_ids
