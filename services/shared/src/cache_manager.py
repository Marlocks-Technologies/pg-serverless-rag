"""
Cache Manager - Caching layer for embeddings, answers, and query results.

Provides DynamoDB-based caching to reduce latency and costs.
"""

import json
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import boto3
from shared.logger import get_logger

logger = get_logger(__name__)


class CacheManager:
    """Manages caching for embeddings, answers, and query results."""

    def __init__(self, table_name: str, region: str = "us-east-1"):
        """
        Initialize cache manager.

        Args:
            table_name: DynamoDB cache table name
            region: AWS region
        """
        self.table_name = table_name
        self.region = region
        dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = dynamodb.Table(table_name)

    def get_embedding_cache(
        self,
        text: str,
        model_id: str
    ) -> Optional[List[float]]:
        """
        Get cached embedding for text.

        Args:
            text: Text to get embedding for
            model_id: Embedding model ID

        Returns:
            Cached embedding or None
        """
        cache_key = self._generate_embedding_key(text, model_id)

        try:
            response = self.table.get_item(
                Key={
                    'CacheKey': cache_key,
                    'CacheType': 'embedding'
                }
            )

            if 'Item' in response:
                item = response['Item']
                # Check if expired
                if self._is_expired(item.get('ExpiresAt')):
                    return None

                logger.info("embedding_cache_hit", key=cache_key[:16])
                return json.loads(item['Value'])

            logger.info("embedding_cache_miss", key=cache_key[:16])
            return None

        except Exception as e:
            logger.error("embedding_cache_error", error=str(e))
            return None

    def set_embedding_cache(
        self,
        text: str,
        model_id: str,
        embedding: List[float],
        ttl_hours: int = 24
    ):
        """
        Cache an embedding.

        Args:
            text: Text the embedding is for
            model_id: Embedding model ID
            embedding: Embedding vector
            ttl_hours: Time-to-live in hours
        """
        cache_key = self._generate_embedding_key(text, model_id)

        try:
            self.table.put_item(
                Item={
                    'CacheKey': cache_key,
                    'CacheType': 'embedding',
                    'Value': json.dumps(embedding),
                    'ModelId': model_id,
                    'CreatedAt': datetime.now(timezone.utc).isoformat(),
                    'ExpiresAt': self._calculate_expiry(ttl_hours),
                    'TTL': self._calculate_ttl(ttl_hours)
                }
            )

            logger.info("embedding_cached", key=cache_key[:16])

        except Exception as e:
            logger.error("embedding_cache_set_error", error=str(e))

    def get_answer_cache(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached answer for question.

        Args:
            question: User's question
            filters: Optional filters used in query

        Returns:
            Cached answer data or None
        """
        cache_key = self._generate_question_key(question, filters)

        try:
            response = self.table.get_item(
                Key={
                    'CacheKey': cache_key,
                    'CacheType': 'answer'
                }
            )

            if 'Item' in response:
                item = response['Item']

                # Check if expired
                if self._is_expired(item.get('ExpiresAt')):
                    return None

                logger.info("answer_cache_hit", key=cache_key[:16])

                return {
                    'answer': item['Answer'],
                    'citations': json.loads(item.get('Citations', '[]')),
                    'metadata': json.loads(item.get('Metadata', '{}'))
                }

            logger.info("answer_cache_miss", key=cache_key[:16])
            return None

        except Exception as e:
            logger.error("answer_cache_error", error=str(e))
            return None

    def set_answer_cache(
        self,
        question: str,
        answer: str,
        citations: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
        ttl_hours: int = 12
    ):
        """
        Cache an answer.

        Args:
            question: User's question
            answer: Generated answer
            citations: Source citations
            metadata: Additional metadata
            filters: Filters used in query
            ttl_hours: Time-to-live in hours
        """
        cache_key = self._generate_question_key(question, filters)

        try:
            self.table.put_item(
                Item={
                    'CacheKey': cache_key,
                    'CacheType': 'answer',
                    'Question': question,
                    'Answer': answer,
                    'Citations': json.dumps(citations),
                    'Metadata': json.dumps(metadata),
                    'Filters': json.dumps(filters) if filters else None,
                    'CreatedAt': datetime.now(timezone.utc).isoformat(),
                    'ExpiresAt': self._calculate_expiry(ttl_hours),
                    'TTL': self._calculate_ttl(ttl_hours),
                    'HitCount': 0
                }
            )

            logger.info("answer_cached", key=cache_key[:16])

        except Exception as e:
            logger.error("answer_cache_set_error", error=str(e))

    def increment_hit_count(self, cache_key: str, cache_type: str):
        """
        Increment cache hit count for analytics.

        Args:
            cache_key: Cache key
            cache_type: Cache type (embedding, answer, etc.)
        """
        try:
            self.table.update_item(
                Key={
                    'CacheKey': cache_key,
                    'CacheType': cache_type
                },
                UpdateExpression='SET HitCount = if_not_exists(HitCount, :zero) + :inc',
                ExpressionAttributeValues={
                    ':zero': 0,
                    ':inc': 1
                }
            )
        except Exception as e:
            logger.warning("hit_count_increment_failed", error=str(e))

    def get_retrieval_cache(
        self,
        query_embedding: List[float],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached retrieval results.

        Args:
            query_embedding: Query embedding vector
            filters: Optional filters
            top_k: Number of results

        Returns:
            Cached retrieval results or None
        """
        # Generate cache key from embedding + filters + top_k
        cache_key = self._generate_retrieval_key(query_embedding, filters, top_k)

        try:
            response = self.table.get_item(
                Key={
                    'CacheKey': cache_key,
                    'CacheType': 'retrieval'
                }
            )

            if 'Item' in response:
                item = response['Item']

                # Check if expired
                if self._is_expired(item.get('ExpiresAt')):
                    return None

                logger.info("retrieval_cache_hit", key=cache_key[:16])
                return json.loads(item['Results'])

            logger.info("retrieval_cache_miss", key=cache_key[:16])
            return None

        except Exception as e:
            logger.error("retrieval_cache_error", error=str(e))
            return None

    def set_retrieval_cache(
        self,
        query_embedding: List[float],
        results: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        ttl_hours: int = 6
    ):
        """
        Cache retrieval results.

        Args:
            query_embedding: Query embedding vector
            results: Retrieval results
            filters: Optional filters
            top_k: Number of results
            ttl_hours: Time-to-live in hours
        """
        cache_key = self._generate_retrieval_key(query_embedding, filters, top_k)

        try:
            self.table.put_item(
                Item={
                    'CacheKey': cache_key,
                    'CacheType': 'retrieval',
                    'Results': json.dumps(results),
                    'TopK': top_k,
                    'Filters': json.dumps(filters) if filters else None,
                    'CreatedAt': datetime.now(timezone.utc).isoformat(),
                    'ExpiresAt': self._calculate_expiry(ttl_hours),
                    'TTL': self._calculate_ttl(ttl_hours)
                }
            )

            logger.info("retrieval_cached", key=cache_key[:16])

        except Exception as e:
            logger.error("retrieval_cache_set_error", error=str(e))

    def invalidate_cache(
        self,
        cache_type: Optional[str] = None,
        pattern: Optional[str] = None
    ) -> int:
        """
        Invalidate cache entries.

        Args:
            cache_type: Optional cache type to invalidate
            pattern: Optional pattern to match cache keys

        Returns:
            Number of items invalidated
        """
        # For now, implement simple scan and delete
        # In production, consider using GSI for efficient invalidation
        count = 0

        try:
            scan_kwargs = {}
            if cache_type:
                scan_kwargs['FilterExpression'] = 'CacheType = :type'
                scan_kwargs['ExpressionAttributeValues'] = {':type': cache_type}

            response = self.table.scan(**scan_kwargs)

            for item in response.get('Items', []):
                if pattern and pattern not in item['CacheKey']:
                    continue

                self.table.delete_item(
                    Key={
                        'CacheKey': item['CacheKey'],
                        'CacheType': item['CacheType']
                    }
                )
                count += 1

            logger.info("cache_invalidated", count=count, type=cache_type)
            return count

        except Exception as e:
            logger.error("cache_invalidation_error", error=str(e))
            return count

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache statistics
        """
        try:
            # Scan for stats (simplified version)
            response = self.table.scan(
                ProjectionExpression='CacheType, HitCount, CreatedAt'
            )

            stats = {
                'total_entries': len(response.get('Items', [])),
                'by_type': {},
                'total_hits': 0
            }

            for item in response.get('Items', []):
                cache_type = item['CacheType']
                hit_count = item.get('HitCount', 0)

                if cache_type not in stats['by_type']:
                    stats['by_type'][cache_type] = {
                        'count': 0,
                        'hits': 0
                    }

                stats['by_type'][cache_type]['count'] += 1
                stats['by_type'][cache_type]['hits'] += hit_count
                stats['total_hits'] += hit_count

            return stats

        except Exception as e:
            logger.error("cache_stats_error", error=str(e))
            return {'error': str(e)}

    def _generate_embedding_key(self, text: str, model_id: str) -> str:
        """Generate cache key for embedding."""
        content = f"{text}:{model_id}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _generate_question_key(
        self,
        question: str,
        filters: Optional[Dict[str, Any]]
    ) -> str:
        """Generate cache key for question."""
        # Normalize question (lowercase, strip)
        normalized = question.lower().strip()

        # Include filters in key
        filter_str = json.dumps(filters, sort_keys=True) if filters else ""
        content = f"{normalized}:{filter_str}"

        return hashlib.sha256(content.encode()).hexdigest()

    def _generate_retrieval_key(
        self,
        query_embedding: List[float],
        filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> str:
        """Generate cache key for retrieval results."""
        # Use first 10 dimensions for key (balance between uniqueness and performance)
        embedding_sample = query_embedding[:10]
        filter_str = json.dumps(filters, sort_keys=True) if filters else ""
        content = f"{embedding_sample}:{filter_str}:{top_k}"

        return hashlib.sha256(content.encode()).hexdigest()

    def _calculate_expiry(self, hours: int) -> str:
        """Calculate expiry timestamp."""
        expiry = datetime.now(timezone.utc) + timedelta(hours=hours)
        return expiry.isoformat()

    def _calculate_ttl(self, hours: int) -> int:
        """Calculate TTL for DynamoDB."""
        expiry = datetime.now(timezone.utc) + timedelta(hours=hours)
        return int(expiry.timestamp())

    def _is_expired(self, expires_at: Optional[str]) -> bool:
        """Check if cache entry is expired."""
        if not expires_at:
            return False

        try:
            expiry = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            return datetime.now(timezone.utc) > expiry
        except Exception:
            return True
