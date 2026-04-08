# Amazon S3 Vectors (boto3 `s3vectors`) — Proper Implementation Guide

This repo currently stores embeddings as JSON objects in a **regular S3 bucket** (`rag-*-kb-vectors`) and performs similarity search by downloading those JSON files and computing cosine similarity in code.

If you want a **proper Amazon S3 Vectors** implementation, you should use the dedicated **S3 Vectors service API** via `boto3.client("s3vectors")`, as documented in AWS boto3 reference: `https://docs.aws.amazon.com/boto3/latest/reference/services/s3vectors.html`.

## What “S3 Vectors” means (AWS service)

Using the S3 Vectors service involves:
- **Vector buckets**: a special bucket type for vectors (not a standard S3 bucket).
- **Indexes**: created inside a vector bucket, defining **dimension** and **distance metric** (e.g. cosine).
- **Vectors**: inserted and queried via API operations such as `put_vectors()` and `query_vectors()`.

From boto3: create a client with:

```python
import boto3
s3vectors = boto3.client("s3vectors")
```

## Recommended target architecture (for this repo)

### Ingestion path (write)

- Document Processor extracts text → chunks → embedding vectors (Titan).
- Store vectors via **S3 Vectors**:
  - `s3vectors.put_vectors(...)` into a named vector bucket + index.
- Store the **citation payload** in vector metadata (documentId, filename, sourceUri, chunkIndex, etc.).

### Retrieval path (read)

- Chat handler embeds the query (Titan).
- Query S3 Vectors with:
  - `s3vectors.query_vectors(...)`
- Convert returned matches into:
  - context window text
  - citations (sourceUri/filename + chunkIndex + score)

## Minimal boto3 flow (create bucket + index)

```python
import boto3

s3vectors = boto3.client("s3vectors")

# 1) Create vector bucket (idempotency depends on your naming strategy)
s3vectors.create_vector_bucket(
    vectorBucketName="rag-dev-vector-bucket"
)

# 2) Create index (dimension must match embedding model output)
s3vectors.create_index(
    vectorBucketName="rag-dev-vector-bucket",
    indexName="rag-dev-index",
    dimension=1024,
    distanceMetric="COSINE"
)
```

## Writing vectors (put)

Use `put_vectors()` to write vectors to an index. Store **citations** in metadata so later retrieval can produce grounded answers.

Example shape (pseudocode; exact request keys should follow the boto3 reference):

```python
import boto3

s3vectors = boto3.client("s3vectors")

s3vectors.put_vectors(
    vectorBucketName="rag-dev-vector-bucket",
    indexName="rag-dev-index",
    vectors=[
        {
            "key": "0a2880ff-...-chunk-0",
            "vector": [0.1, 0.2, "..."],  # 1024 floats
            "metadata": {
                "documentId": "0a2880ff-...",
                "filename": "01_Constitution_Nigeria_1999.pdf",
                "sourceUri": "s3://rag-dev-doc-staging/grouped/unknown/0a2880ff-....pdf",
                "chunkIndex": 0,
                "category": "unknown"
            }
        }
    ]
)
```

## Querying vectors (similarity search)

Use `query_vectors()` to retrieve nearest neighbors in the index:

```python
import boto3

s3vectors = boto3.client("s3vectors")

resp = s3vectors.query_vectors(
    vectorBucketName="rag-dev-vector-bucket",
    indexName="rag-dev-index",
    queryVector=[0.01, 0.02, "..."],  # 1024 floats
    topK=5,
)

# resp should contain matches with scores + metadata
```

## Listing and debugging

The boto3 reference also documents:
- `list_vector_buckets()`
- `list_indexes()`
- `list_vectors()` (paginator supported)
- `get_vectors()` for debugging specific keys

These are useful to validate that vectors were actually inserted and are queryable.

## IAM permissions

Your Lambda role needs S3 Vectors permissions aligned with the boto3 methods you call (examples):
- `s3vectors:CreateVectorBucket`, `s3vectors:CreateIndex` (provisioning)
- `s3vectors:PutVectors` (ingestion)
- `s3vectors:QueryVectors`, `s3vectors:GetVectors`, `s3vectors:ListVectors` (retrieval/debug)

## What to update in this repo

To migrate from “S3 JSON vectors” → “S3 Vectors service”:

- Replace the current `S3VectorStore` implementation (`services/shared/src/shared/s3_vectors.py`) to use:
  - `boto3.client("s3vectors")`
  - `put_vectors()` and `query_vectors()` instead of S3 `put_object/get_object`.
- Update docs to avoid calling the current approach “Amazon S3 Vectors” unless it truly uses the S3 Vectors API.

