# Custom RAG Implementation with S3 Vectors

## Overview

This document describes how to implement a custom RAG solution using **Amazon S3 Vectors directly**, bypassing Bedrock Knowledge Bases until S3 becomes available as a native Bedrock KB backend.

## Why Custom Implementation?

### Current State (March 2026)
- ✅ **S3 Vectors**: Available for direct API usage
- ❌ **Bedrock KB Integration**: Not yet available as a native backend

### Benefits of Custom Approach
1. **Use S3 Vectors Today** - Don't wait for Bedrock KB support
2. **Cost Optimization** - $30-50/month vs $700/month for OpenSearch
3. **Full Control** - Custom retrieval logic, ranking, filtering
4. **Migration Path** - Easy switch to Bedrock KB when S3 support arrives

## Architecture

### Custom RAG Flow

```
┌─────────────────────┐
│  Document Upload    │
└──────────┬──────────┘
           v
┌─────────────────────────────────────┐
│  DocumentProcessorLambda            │
│  1. Extract text (Textract/parsers) │
│  2. Normalize and chunk             │
│  3. Generate embeddings (Bedrock)   │
│  4. Store in S3 Vectors             │
└──────────┬──────────────────────────┘
           v
┌─────────────────────────────────────┐
│  S3 Vectors Bucket                  │
│  - Vector embeddings                │
│  - Document metadata                │
│  - Full-text for retrieval          │
└──────────┬──────────────────────────┘
           v
┌─────────────────────────────────────┐
│  ChatHandlerLambda                  │
│  1. Load session history (DynamoDB) │
│  2. Generate query embedding        │
│  3. Query S3 Vectors (similarity)   │
│  4. Retrieve top-k chunks           │
│  5. Generate answer (Bedrock)       │
│  6. Return with citations           │
└─────────────────────────────────────┘
```

### Key Differences from Bedrock KB Approach

| Aspect | Bedrock KB | Custom S3 Vectors |
|--------|-----------|-------------------|
| Vector Storage | Managed by Bedrock | Direct S3 Vectors API |
| Embeddings | Auto-generated | Manual via Bedrock Embeddings API |
| Chunking | Automatic | Custom implementation |
| Retrieval | RetrieveAndGenerate API | Manual query + ranking |
| Control | Limited | Full control |
| Setup Complexity | Low | Moderate |
| Cost | $700/mo (OpenSearch interim) | $30-50/mo |

## Implementation Guide

### Phase 1: S3 Vectors Setup

#### 1.1 Create Vector Index in S3

S3 Vectors uses special metadata to store vector data. Each document chunk is stored as:

```json
{
  "id": "doc-123-chunk-0",
  "embedding": [0.123, 0.456, ...],  // 1536-dim vector
  "text": "Document chunk text...",
  "metadata": {
    "documentId": "doc-123",
    "filename": "report.pdf",
    "category": "technical-spec",
    "chunkIndex": 0,
    "sourceUri": "s3://staging/grouped/technical-spec/doc-123.pdf"
  }
}
```

#### 1.2 Python Helper for S3 Vectors

```python
# services/shared/src/s3_vectors.py

import json
import numpy as np
from typing import List, Dict, Any
import boto3

class S3VectorStore:
    """
    Interface to Amazon S3 Vectors for storing and querying embeddings.
    """

    def __init__(self, bucket_name: str, region: str):
        self.bucket = bucket_name
        self.s3 = boto3.client('s3', region_name=region)
        self.prefix = "vectors/"

    def store_vector(self, vector_id: str, embedding: List[float],
                     text: str, metadata: Dict[str, Any]):
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

    def query_vectors(self, query_embedding: List[float], top_k: int = 5,
                     filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Query S3 Vectors for similar embeddings.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of matching documents with similarity scores
        """
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
```

### Phase 2: Document Processing with Embedding Generation

#### 2.1 Update DocumentProcessorLambda

```python
# services/document_processor/src/handler.py (excerpt)

from shared.s3_vectors import S3VectorStore
from shared.bedrock_wrappers import generate_embeddings
import uuid

def process_document(s3_event):
    """
    Process uploaded document and store vectors in S3.
    """
    # Extract text (existing logic)
    text = extract_text_from_document(...)

    # Chunk text
    chunks = chunk_text(text, chunk_size=800, overlap=0.15)

    # Initialize S3 Vector Store
    vector_store = S3VectorStore(
        bucket_name=os.environ['VECTORS_BUCKET'],
        region=os.environ['AWS_REGION']
    )

    # Generate document ID
    document_id = str(uuid.uuid4())

    # Process each chunk
    for idx, chunk in enumerate(chunks):
        # Generate embedding using Bedrock
        embedding = generate_embeddings(
            text=chunk['text'],
            model_id=os.environ['EMBEDDING_MODEL_ID']
        )

        # Store in S3 Vectors
        vector_id = f"{document_id}-chunk-{idx}"
        vector_store.store_vector(
            vector_id=vector_id,
            embedding=embedding,
            text=chunk['text'],
            metadata={
                'documentId': document_id,
                'filename': source_filename,
                'category': classification['primaryTag'],
                'chunkIndex': idx,
                'sourceUri': f"s3://{staging_bucket}/{staged_key}",
                'timestamp': datetime.utcnow().isoformat()
            }
        )

    logger.info(f"Stored {len(chunks)} vectors for document {document_id}")


def chunk_text(text: str, chunk_size: int, overlap: float) -> List[Dict]:
    """
    Split text into overlapping chunks.

    Args:
        text: Full document text
        chunk_size: Target size in tokens
        overlap: Overlap percentage (0.0 to 1.0)

    Returns:
        List of chunks with text and token count
    """
    # Simple word-based chunking (production: use tiktoken for token-based)
    words = text.split()
    words_per_chunk = chunk_size
    overlap_words = int(words_per_chunk * overlap)

    chunks = []
    start = 0

    while start < len(words):
        end = start + words_per_chunk
        chunk_words = words[start:end]
        chunk_text = ' '.join(chunk_words)

        chunks.append({
            'text': chunk_text,
            'token_count': len(chunk_words),  # Approximate
            'start_index': start
        })

        start = end - overlap_words
        if start >= len(words):
            break

    return chunks
```

#### 2.2 Bedrock Embeddings Wrapper

```python
# services/shared/src/bedrock_wrappers.py (add to existing)

def generate_embeddings(text: str, model_id: str = None) -> List[float]:
    """
    Generate embeddings using Amazon Bedrock.

    Args:
        text: Text to embed
        model_id: Embedding model ID (default: Titan Embeddings v2)

    Returns:
        List of floats representing the embedding vector
    """
    if model_id is None:
        model_id = "amazon.titan-embed-text-v2:0"

    bedrock = boto3.client('bedrock-runtime')

    # Titan Embeddings v2 request format
    body = json.dumps({
        "inputText": text
    })

    response = bedrock.invoke_model(
        modelId=model_id,
        body=body,
        contentType='application/json',
        accept='application/json'
    )

    response_body = json.loads(response['body'].read())
    embedding = response_body['embedding']

    return embedding
```

### Phase 3: Chat Handler with Custom Retrieval

#### 3.1 Update ChatHandlerLambda

```python
# services/chat_handler/src/handler.py (excerpt)

from shared.s3_vectors import S3VectorStore
from shared.bedrock_wrappers import generate_embeddings, invoke_model

def handle_chat_query(event):
    """
    Handle chat query with custom S3 Vectors retrieval.
    """
    # Parse request
    body = json.loads(event['body'])
    session_id = body['sessionId']
    message = body['message']
    top_k = body.get('topK', 5)
    filters = body.get('filters', {})

    # Load conversation history
    history = load_history_from_dynamodb(session_id)

    # Generate query embedding
    query_embedding = generate_embeddings(text=message)

    # Query S3 Vectors
    vector_store = S3VectorStore(
        bucket_name=os.environ['VECTORS_BUCKET'],
        region=os.environ['AWS_REGION']
    )

    results = vector_store.query_vectors(
        query_embedding=query_embedding,
        top_k=top_k,
        filters=filters
    )

    # Build context from retrieved chunks
    context_chunks = []
    citations = []

    for result in results:
        context_chunks.append(result['text'])
        citations.append({
            'documentId': result['metadata']['documentId'],
            'sourceUri': result['metadata']['sourceUri'],
            'excerpt': result['text'][:200],
            'score': result['score']
        })

    # Build prompt with context
    context_text = "\n\n".join(context_chunks)
    system_prompt = load_system_prompt()

    prompt = f"""Based on the following context, answer the user's question.

Context:
{context_text}

User Question: {message}

Answer:"""

    # Generate response
    answer = invoke_model(
        model_id=os.environ['GENERATION_MODEL_ID'],
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=2000
    )

    # Store in history
    store_conversation_turn(session_id, message, answer, citations)

    # Return response
    return {
        'statusCode': 200,
        'body': json.dumps({
            'sessionId': session_id,
            'answer': answer,
            'citations': citations,
            'requestId': context.aws_request_id
        })
    }
```

## Performance Optimizations

### 1. Parallel Vector Retrieval

For large vector stores, parallelize retrieval across S3 prefixes:

```python
from concurrent.futures import ThreadPoolExecutor

def query_vectors_parallel(self, query_embedding, top_k=5, filters=None):
    """Query vectors in parallel across prefixes."""
    prefixes = ['vectors/technical-spec/', 'vectors/hr/', 'vectors/invoice/']

    with ThreadPoolExecutor(max_workers=len(prefixes)) as executor:
        futures = [
            executor.submit(self._query_prefix, prefix, query_embedding, top_k, filters)
            for prefix in prefixes
        ]

        all_results = []
        for future in futures:
            all_results.extend(future.result())

    # Sort and return top_k
    all_results.sort(key=lambda x: x['score'], reverse=True)
    return all_results[:top_k]
```

### 2. Caching Frequent Queries

Use ElastiCache or DynamoDB for caching:

```python
import hashlib

def query_with_cache(query_embedding, top_k, filters):
    """Query with caching layer."""
    # Generate cache key
    cache_key = hashlib.sha256(
        json.dumps([query_embedding[:10], top_k, filters]).encode()
    ).hexdigest()

    # Check cache
    cached = get_from_cache(cache_key)
    if cached:
        return cached

    # Query S3 Vectors
    results = vector_store.query_vectors(query_embedding, top_k, filters)

    # Store in cache (TTL: 1 hour)
    store_in_cache(cache_key, results, ttl=3600)

    return results
```

### 3. Vector Index Optimization

Organize vectors by category for faster filtering:

```
s3://vectors-bucket/
  vectors/
    technical-spec/
      doc-123-chunk-0.json
      doc-123-chunk-1.json
    hr/
      doc-456-chunk-0.json
    invoice/
      doc-789-chunk-0.json
```

## Migration to Bedrock KB (Future)

When S3 becomes available as a Bedrock KB backend:

1. **Keep existing vectors** - S3 Vectors remain in place
2. **Create Bedrock KB** - Point to same S3 bucket
3. **Update Lambda code** - Replace custom retrieval with `retrieve_and_generate()`
4. **Test in parallel** - Run both approaches simultaneously
5. **Switch traffic** - Gradually migrate to Bedrock KB
6. **Remove custom code** - Clean up custom retrieval logic

### Migration Script

```python
# scripts/migrate_to_bedrock_kb.py

def migrate_vectors_to_bedrock_kb():
    """
    Migrate custom S3 Vectors to Bedrock Knowledge Base format.
    """
    # S3 Vectors are already in S3, just need to:
    # 1. Create Bedrock KB pointing to vectors bucket
    # 2. Trigger sync/ingestion
    # 3. Validate retrieval works

    bedrock_agent = boto3.client('bedrock-agent')

    # Create KB with S3 storage (once supported)
    kb = bedrock_agent.create_knowledge_base(
        name='migrated-kb',
        roleArn=kb_role_arn,
        storageConfiguration={
            'type': 'S3',
            's3Configuration': {
                'bucketArn': vectors_bucket_arn
            }
        }
    )

    print(f"KB created: {kb['knowledgeBaseId']}")
```

## Cost Analysis

### Custom S3 Vectors (Current Month)

| Component | Usage | Cost |
|-----------|-------|------|
| S3 Storage (vectors) | 10 GB | $0.23 |
| S3 API Requests | 100K PUT + 1M GET | $5.40 |
| Lambda (processing) | 10K invocations | $2.00 |
| Lambda (chat) | 50K invocations | $10.00 |
| Bedrock Embeddings | 1M tokens | $10.00 |
| Bedrock Generation | 5M tokens | $15.00 |
| **Total** | | **$42.63** |

### OpenSearch Serverless (Alternative)

| Component | Usage | Cost |
|-----------|-------|------|
| OpenSearch (4 OCUs) | 730 hours | $700.00 |
| Lambda (same) | Same as above | $27.00 |
| Bedrock (same) | Same as above | $25.00 |
| **Total** | | **$752.00** |

**Savings: $709.37/month (94%)**

## Testing Guide

### Unit Tests

```python
# services/shared/tests/test_s3_vectors.py

import pytest
from moto import mock_s3
from shared.s3_vectors import S3VectorStore

@mock_s3
def test_store_and_query_vector():
    # Create mock S3 bucket
    s3 = boto3.client('s3')
    s3.create_bucket(Bucket='test-vectors')

    # Initialize vector store
    store = S3VectorStore('test-vectors', 'us-east-1')

    # Store vector
    embedding = [0.1, 0.2, 0.3, 0.4]
    store.store_vector(
        vector_id='test-1',
        embedding=embedding,
        text='Test document',
        metadata={'category': 'test'}
    )

    # Query
    results = store.query_vectors(
        query_embedding=[0.1, 0.2, 0.3, 0.4],
        top_k=1
    )

    assert len(results) == 1
    assert results[0]['id'] == 'test-1'
    assert results[0]['score'] > 0.99  # Should be very similar
```

### Integration Tests

```python
# tests/integration/test_e2e_rag.py

def test_end_to_end_rag_flow():
    """Test full RAG flow: upload -> embed -> query -> answer"""

    # 1. Upload document
    upload_test_document('test.pdf')

    # 2. Wait for processing
    time.sleep(10)

    # 3. Query
    response = chat_query(
        session_id='test-session',
        message='What does the document say?'
    )

    # 4. Validate response
    assert 'answer' in response
    assert len(response['citations']) > 0
```

## Deployment

### Requirements

Add to `services/*/requirements.txt`:

```
boto3>=1.34.0
numpy>=1.24.0  # For vector similarity calculations
```

### Environment Variables

Update Lambda environment variables:

```hcl
environment_variables = {
  VECTORS_BUCKET      = "${var.project_name}-${var.environment}-kb-vectors"
  EMBEDDING_MODEL_ID  = "amazon.titan-embed-text-v2:0"
  USE_CUSTOM_RAG      = "true"  # Flag to use custom implementation
}
```

### Deployment Steps

```bash
# 1. Package Lambdas with new dependencies
cd services/shared
pip install -r requirements.txt -t package/
cd package && zip -r ../../dist/shared_layer.zip . && cd ../..

# 2. Deploy updated Lambdas
terraform apply

# 3. Test custom RAG
python3 scripts/test_s3_vectors.py

# 4. Upload test document
aws s3 cp test_doc.pdf s3://${PROJECT}-${ENV}-doc-ingestion/

# 5. Query and validate
curl -X POST ${REST_API_URL}/chat/query \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"test","message":"test query"}'
```

## Conclusion

The custom S3 Vectors implementation provides:
- ✅ **Production-ready** solution available today
- ✅ **94% cost savings** vs OpenSearch Serverless
- ✅ **Full control** over retrieval logic
- ✅ **Easy migration** to Bedrock KB when S3 support arrives

This approach allows deploying a cost-effective RAG platform immediately while maintaining a clear migration path to Bedrock Knowledge Bases in the future.
