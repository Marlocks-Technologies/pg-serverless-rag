"""
Integration tests for Phase 3 RAG implementation.

Tests query processing, retrieval, and answer generation.
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add shared library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared/src'))

from query_processor import QueryProcessor
from retrieval_service import RetrievalService, RetrievalResult
from rag_engine import RAGEngine


def test_query_processor_normalization():
    """Test query normalization."""
    processor = QueryProcessor()

    # Test filler word removal
    query = "Please tell me what is RAG?"
    normalized = processor._normalize_query(query)
    assert "please" not in normalized.lower()
    assert "what is rag?" in normalized.lower()

    # Test whitespace normalization
    query = "What    is    RAG     architecture?"
    normalized = processor._normalize_query(query)
    assert "  " not in normalized


def test_query_processor_intent_detection():
    """Test query intent detection."""
    processor = QueryProcessor()

    # Factual query
    assert processor._detect_intent("What is a vector database?") == "factual"

    # Procedural query
    assert processor._detect_intent("How to deploy the application?") == "procedural"

    # Analytical query
    assert processor._detect_intent("Compare S3 and OpenSearch") == "analytical"

    # Listing query
    assert processor._detect_intent("List all supported document types") == "listing"


def test_query_processor_keyword_extraction():
    """Test keyword extraction."""
    processor = QueryProcessor()

    query = "What is the architecture of the RAG platform?"
    keywords = processor.extract_keywords(query)

    assert "architecture" in keywords
    assert "rag" in keywords
    assert "platform" in keywords
    assert "the" not in keywords  # Stop word
    assert "is" not in keywords   # Stop word


@patch('query_processor.generate_embeddings')
@patch('query_processor.boto3')
def test_query_processor_process_query(mock_boto3, mock_generate_embeddings):
    """Test full query processing."""
    # Mock embedding generation
    mock_embedding = [0.1] * 1536
    mock_generate_embeddings.return_value = mock_embedding

    # Mock boto3 client
    mock_client = Mock()
    mock_boto3.client.return_value = mock_client

    processor = QueryProcessor()

    result = processor.process_query(
        query="What is RAG architecture?",
        filters={"category": "technical-spec"},
        top_k=5
    )

    assert result['normalized_query']
    assert len(result['embedding']) == 1536
    assert result['filters'] == {"category": "technical-spec"}
    assert result['top_k'] == 5
    assert 'query_metadata' in result


def test_retrieval_result_citation():
    """Test citation generation from retrieval result."""
    chunk_data = {
        'id': 'doc-123_chunk-0',
        'text': 'Sample text content',
        'metadata': {
            'filename': 'architecture.pdf',
            'documentId': 'doc-123',
            'category': 'technical-spec',
            'chunkIndex': 0
        }
    }

    result = RetrievalResult(chunk_data=chunk_data, score=0.85, rank=1)

    citation = result.get_citation()

    assert citation['source'] == 'architecture.pdf'
    assert citation['documentId'] == 'doc-123'
    assert citation['category'] == 'technical-spec'
    assert citation['chunkIndex'] == 0
    assert citation['score'] == 0.85


def test_retrieval_service_context_window():
    """Test context window assembly."""
    service = RetrievalService(vectors_bucket="test-bucket")

    # Create mock results
    results = [
        RetrievalResult(
            chunk_data={
                'id': f'doc-{i}_chunk-0',
                'text': f'Content {i}' * 100,
                'metadata': {'filename': f'doc{i}.pdf'}
            },
            score=0.9 - (i * 0.1),
            rank=i + 1
        )
        for i in range(5)
    ]

    context = service.get_context_window(results, max_tokens=500)

    assert len(context) > 0
    assert "Content 0" in context
    assert "[Source:" in context


def test_retrieval_service_citation_generation():
    """Test citation list generation."""
    service = RetrievalService(vectors_bucket="test-bucket")

    results = [
        RetrievalResult(
            chunk_data={
                'id': f'doc-123_chunk-{i}',
                'text': f'Content {i}',
                'metadata': {
                    'filename': 'test.pdf',
                    'documentId': 'doc-123',
                    'category': 'technical-spec',
                    'chunkIndex': i
                }
            },
            score=0.9,
            rank=i + 1
        )
        for i in range(3)
    ]

    citations = service.generate_citations(results)

    assert len(citations) == 3
    assert all('source' in c for c in citations)
    assert all('score' in c for c in citations)


@patch('rag_engine.invoke_model')
@patch('rag_engine.RetrievalService')
@patch('rag_engine.QueryProcessor')
def test_rag_engine_query(mock_query_processor, mock_retrieval_service, mock_invoke_model):
    """Test RAG engine query flow."""
    # Mock query processor
    mock_processor_instance = Mock()
    mock_processor_instance.process_query.return_value = {
        'normalized_query': 'what is rag',
        'embedding': [0.1] * 1536,
        'filters': None,
        'top_k': 5,
        'query_metadata': {
            'original_query': 'What is RAG?',
            'intent': 'factual',
            'query_length': 12
        }
    }
    mock_query_processor.return_value = mock_processor_instance

    # Mock retrieval service
    mock_retrieval_instance = Mock()
    mock_results = [
        RetrievalResult(
            chunk_data={
                'id': 'doc-1_chunk-0',
                'text': 'RAG stands for Retrieval Augmented Generation',
                'metadata': {'filename': 'guide.pdf', 'documentId': 'doc-1', 'category': 'technical-spec', 'chunkIndex': 0}
            },
            score=0.95,
            rank=1
        )
    ]
    mock_retrieval_instance.retrieve_with_reranking.return_value = mock_results
    mock_retrieval_instance.get_context_window.return_value = "RAG stands for Retrieval Augmented Generation"
    mock_retrieval_instance.generate_citations.return_value = [
        {'source': 'guide.pdf', 'documentId': 'doc-1', 'category': 'technical-spec', 'chunkIndex': 0, 'score': 0.95}
    ]
    mock_retrieval_service.return_value = mock_retrieval_instance

    # Mock answer generation
    mock_invoke_model.return_value = "RAG is a technique that combines retrieval and generation."

    # Create RAG engine
    engine = RAGEngine(
        vectors_bucket='test-bucket',
        region='us-east-1'
    )

    # Execute query
    result = engine.query(
        question="What is RAG?",
        filters=None,
        top_k=5,
        include_citations=True,
        stream=False
    )

    # Verify result structure
    assert 'answer' in result
    assert 'citations' in result
    assert 'metadata' in result
    assert result['metadata']['chunks_retrieved'] == 1


def test_rag_engine_system_prompt():
    """Test system prompt generation."""
    engine = RAGEngine(vectors_bucket='test-bucket', region='us-east-1')

    system_prompt = engine._build_system_prompt()

    assert "helpful AI assistant" in system_prompt
    assert "context" in system_prompt.lower()
    assert "citations" in system_prompt.lower()


def test_rag_engine_user_prompt():
    """Test user prompt formatting."""
    engine = RAGEngine(vectors_bucket='test-bucket', region='us-east-1')

    context = "Sample context about RAG"
    question = "What is RAG?"

    user_prompt = engine._build_user_prompt(question, context)

    assert context in user_prompt
    assert question in user_prompt
    assert "Context from knowledge base" in user_prompt


@patch('rag_engine.invoke_model')
@patch('rag_engine.boto3')
def test_rag_engine_answer_generation(mock_boto3, mock_invoke_model):
    """Test answer generation."""
    mock_client = Mock()
    mock_boto3.client.return_value = mock_client
    mock_invoke_model.return_value = "This is the answer."

    engine = RAGEngine(vectors_bucket='test-bucket', region='us-east-1')

    answer = engine._generate_answer(
        question="What is RAG?",
        context="RAG is Retrieval Augmented Generation"
    )

    assert answer == "This is the answer."
    mock_invoke_model.assert_called_once()


def test_query_expansion():
    """Test query expansion for better recall."""
    processor = QueryProcessor()

    variations = processor.expand_query("What is the document process?")

    assert len(variations) > 1
    # Should include variations with synonyms
    assert any('procedure' in v.lower() for v in variations)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
