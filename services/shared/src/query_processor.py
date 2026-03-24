"""
Query Processor - Prepares user queries for vector search.

Handles query normalization, embedding generation, and query optimization.
"""

import re
from typing import Dict, List, Optional, Any
from bedrock_wrappers import generate_embeddings


class QueryProcessor:
    """Process and prepare user queries for RAG retrieval."""

    def __init__(self, embedding_model_id: str = "amazon.titan-embed-text-v2:0", region: str = "us-east-1"):
        """
        Initialize query processor.

        Args:
            embedding_model_id: Bedrock embedding model ID
            region: AWS region
        """
        self.embedding_model_id = embedding_model_id
        self.region = region
        import boto3
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region)

    def process_query(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Process a query for vector search.

        Args:
            query: User's natural language query
            filters: Optional metadata filters (e.g., {"category": "technical-spec"})
            top_k: Number of results to retrieve

        Returns:
            Dict containing:
                - normalized_query: Cleaned query text
                - embedding: Query embedding vector
                - filters: Applied filters
                - top_k: Number of results to return
                - query_metadata: Additional query metadata
        """
        # Normalize query
        normalized = self._normalize_query(query)

        # Detect query intent
        intent = self._detect_intent(normalized)

        # Generate embedding
        embedding = generate_embeddings(
            text=normalized,
            model_id=self.embedding_model_id,
            client=self.bedrock_client
        )

        # Apply automatic filters based on intent
        enhanced_filters = self._enhance_filters(filters, intent)

        return {
            'normalized_query': normalized,
            'embedding': embedding,
            'filters': enhanced_filters,
            'top_k': top_k,
            'query_metadata': {
                'original_query': query,
                'intent': intent,
                'query_length': len(normalized)
            }
        }

    def _normalize_query(self, query: str) -> str:
        """
        Normalize query text.

        Args:
            query: Raw query string

        Returns:
            Normalized query
        """
        # Remove extra whitespace
        normalized = ' '.join(query.split())

        # Remove common filler words at start
        filler_patterns = [
            r'^(please\s+)',
            r'^(can\s+you\s+)',
            r'^(could\s+you\s+)',
            r'^(i\s+want\s+to\s+know\s+)',
            r'^(tell\s+me\s+)',
            r'^(show\s+me\s+)',
        ]

        for pattern in filler_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)

        # Ensure it ends with question mark for question-like queries
        if self._is_question(normalized) and not normalized.endswith('?'):
            normalized += '?'

        return normalized.strip()

    def _is_question(self, text: str) -> bool:
        """Check if text is a question."""
        question_words = ['what', 'when', 'where', 'who', 'why', 'how', 'which', 'whose']
        first_word = text.lower().split()[0] if text.split() else ''
        return first_word in question_words or text.endswith('?')

    def _detect_intent(self, query: str) -> str:
        """
        Detect query intent for optimization.

        Args:
            query: Normalized query

        Returns:
            Intent category (e.g., 'factual', 'procedural', 'analytical', 'general')
        """
        query_lower = query.lower()

        # Factual queries (definitions, specific facts)
        if any(word in query_lower for word in ['what is', 'define', 'definition', 'meaning of']):
            return 'factual'

        # Procedural queries (how-to, steps, instructions)
        if any(word in query_lower for word in ['how to', 'how do', 'steps', 'process', 'procedure']):
            return 'procedural'

        # Analytical queries (comparisons, analysis, evaluation)
        if any(word in query_lower for word in ['compare', 'difference', 'analyze', 'evaluate', 'why']):
            return 'analytical'

        # Listing queries
        if any(word in query_lower for word in ['list', 'enumerate', 'what are', 'which are']):
            return 'listing'

        return 'general'

    def _enhance_filters(
        self,
        filters: Optional[Dict[str, Any]],
        intent: str
    ) -> Optional[Dict[str, Any]]:
        """
        Enhance filters based on query intent.

        Args:
            filters: Existing filters
            intent: Detected query intent

        Returns:
            Enhanced filters
        """
        if filters is None:
            filters = {}

        # For procedural queries, prioritize technical specs and operations docs
        if intent == 'procedural' and 'category' not in filters:
            filters['category'] = ['technical-spec', 'operations']

        # For factual queries, cast a wider net
        if intent == 'factual':
            # Don't restrict category for factual queries
            pass

        return filters if filters else None

    def extract_keywords(self, query: str) -> List[str]:
        """
        Extract important keywords from query.

        Args:
            query: Query text

        Returns:
            List of keywords
        """
        # Remove stop words
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'you', 'your', 'what', 'when',
            'where', 'who', 'why', 'how', 'can', 'could', 'should'
        }

        # Tokenize and filter
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return keywords

    def expand_query(self, query: str) -> List[str]:
        """
        Generate query variations for better recall.

        Args:
            query: Original query

        Returns:
            List of query variations
        """
        variations = [query]

        # Add question mark variation
        if not query.endswith('?') and self._is_question(query):
            variations.append(query + '?')
        elif query.endswith('?'):
            variations.append(query.rstrip('?'))

        # Add variations with common synonyms
        synonym_map = {
            'document': ['doc', 'file', 'record'],
            'process': ['procedure', 'workflow', 'method'],
            'system': ['platform', 'service', 'application'],
            'error': ['issue', 'problem', 'bug'],
        }

        query_lower = query.lower()
        for term, synonyms in synonym_map.items():
            if term in query_lower:
                for synonym in synonyms:
                    variation = re.sub(
                        r'\b' + term + r'\b',
                        synonym,
                        query,
                        flags=re.IGNORECASE
                    )
                    if variation != query:
                        variations.append(variation)

        return list(set(variations))[:5]  # Limit to 5 variations
