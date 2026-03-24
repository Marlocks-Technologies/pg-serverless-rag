"""
S3 Vectors - Interface to Amazon S3 for vector storage and retrieval.

Provides a simple API for storing and querying vector embeddings using S3.
Phase 5: Optimized with parallel downloads for improved retrieval performance.
"""

import json
import numpy as np
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3


class S3VectorStore:
    """
    Interface to Amazon S3 Vectors for storing and querying embeddings.
    """

    def __init__(self, bucket_name: str, region: str, max_workers: int = 10):
        """
        Initialize S3 Vector Store.

        Args:
            bucket_name: S3 bucket for vector storage
            region: AWS region
            max_workers: Maximum parallel download workers (Phase 5)
        """
        self.bucket = bucket_name
        self.s3 = boto3.client('s3', region_name=region)
        self.prefix = "vectors/"
        self.max_workers = max_workers

    def store_vector(
        self,
        vector_id: str,
        embedding: List[float],
        text: str,
        metadata: Dict[str, Any]
    ):
        """
        Store a vector embedding in S3 with metadata.

        Args:
            vector_id: Unique identifier for this vector
            embedding: Vector embedding (list of floats)
            text: Original text chunk
            metadata: Additional metadata
        """
        key = f"{self.prefix}{vector_id}.json"

        document = {
            "id": vector_id,
            "embedding": embedding,
            "text": text,
            "metadata": metadata
        }

        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(document),
            ContentType='application/json',
            Metadata={
                'vector-dimension': str(len(embedding)),
                'document-id': metadata.get('documentId', ''),
                'category': metadata.get('category', '')
            }
        )

    def query_vectors(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Dict[str, Any] = None,
        use_parallel: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Query S3 Vectors for similar embeddings.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filters: Optional metadata filters
            use_parallel: Use parallel downloads (Phase 5 optimization)

        Returns:
            List of matching documents with similarity scores
        """
        if use_parallel:
            return self._query_vectors_parallel(query_embedding, top_k, filters)
        else:
            return self._query_vectors_sequential(query_embedding, top_k, filters)

    def _query_vectors_sequential(
        self,
        query_embedding: List[float],
        top_k: int,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Original sequential implementation."""
        # List all vectors with prefix
        paginator = self.s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket, Prefix=self.prefix)

        results = []

        for page in pages:
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                # Download and parse vector
                response = self.s3.get_object(Bucket=self.bucket, Key=obj['Key'])
                doc = json.loads(response['Body'].read())

                # Apply filters
                if filters and not self._matches_filters(doc['metadata'], filters):
                    continue

                # Calculate cosine similarity
                similarity = self._cosine_similarity(
                    query_embedding,
                    doc['embedding']
                )

                results.append({
                    'id': doc['id'],
                    'text': doc['text'],
                    'metadata': doc['metadata'],
                    'score': similarity
                })

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def _query_vectors_parallel(
        self,
        query_embedding: List[float],
        top_k: int,
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Phase 5: Parallel implementation using ThreadPoolExecutor.

        Significantly faster for large vector sets (>100 vectors).
        """
        # List all vector keys
        paginator = self.s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket, Prefix=self.prefix)

        keys = []
        for page in pages:
            if 'Contents' in page:
                keys.extend([obj['Key'] for obj in page['Contents']])

        # Download and process vectors in parallel
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_key = {
                executor.submit(self._download_and_process_vector, key, query_embedding, filters): key
                for key in keys
            }

            # Collect results as they complete
            for future in as_completed(future_to_key):
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    # Log error but continue processing other vectors
                    key = future_to_key[future]
                    print(f"Error processing {key}: {e}")

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def _download_and_process_vector(
        self,
        key: str,
        query_embedding: List[float],
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Download and process a single vector.

        Args:
            key: S3 object key
            query_embedding: Query embedding vector
            filters: Optional metadata filters

        Returns:
            Processed result or None if filtered out
        """
        try:
            # Download vector
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            doc = json.loads(response['Body'].read())

            # Apply filters
            if filters and not self._matches_filters(doc['metadata'], filters):
                return None

            # Calculate cosine similarity
            similarity = self._cosine_similarity(
                query_embedding,
                doc['embedding']
            )

            return {
                'id': doc['id'],
                'text': doc['text'],
                'metadata': doc['metadata'],
                'score': similarity
            }

        except Exception as e:
            # Return None on error
            return None

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    def _matches_filters(self, metadata: Dict, filters: Dict) -> bool:
        """Check if metadata matches filters."""
        for key, value in filters.items():
            if key not in metadata:
                return False
            if isinstance(value, list):
                if metadata[key] not in value:
                    return False
            elif metadata[key] != value:
                return False
        return True

    def delete_vector(self, vector_id: str):
        """Delete a vector from S3."""
        key = f"{self.prefix}{vector_id}.json"
        self.s3.delete_object(Bucket=self.bucket, Key=key)

    def list_vectors(self, prefix_filter: str = "") -> List[str]:
        """List all vector IDs with optional prefix filter."""
        full_prefix = f"{self.prefix}{prefix_filter}"
        paginator = self.s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket, Prefix=full_prefix)

        vector_ids = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Extract vector ID from key
                    key = obj['Key']
                    vector_id = key.replace(self.prefix, '').replace('.json', '')
                    vector_ids.append(vector_id)

        return vector_ids

    def batch_store_vectors(self, vectors: List[Dict[str, Any]]):
        """
        Store multiple vectors in batch.

        Args:
            vectors: List of dicts with keys: vector_id, embedding, text, metadata
        """
        for vector in vectors:
            self.store_vector(
                vector_id=vector['vector_id'],
                embedding=vector['embedding'],
                text=vector['text'],
                metadata=vector['metadata']
            )

    def get_vector_count(self) -> int:
        """Get total number of vectors stored."""
        return len(self.list_vectors())

    def clear_vectors(self, confirm: bool = False):
        """
        Delete all vectors. USE WITH CAUTION.

        Args:
            confirm: Must be True to execute
        """
        if not confirm:
            raise ValueError("Must explicitly confirm to clear all vectors")

        vector_ids = self.list_vectors()
        for vector_id in vector_ids:
            self.delete_vector(vector_id)
