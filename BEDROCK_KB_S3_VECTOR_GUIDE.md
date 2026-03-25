# Bedrock Knowledge Base with S3 Vectors (Boto3 + Terraform Guide)

## Overview
This guide explains how to implement an Amazon Bedrock Knowledge Base using:
- S3 as the data source
- S3 Vectors as the vector store
- Boto3 for programmatic setup
- Terraform for infrastructure provisioning

---

## Prerequisites

You need the following resources:

- IAM Role ARN for Bedrock Knowledge Base
- S3 bucket (documents source)
- S3 Vector bucket
- S3 Vector index
- Embedding model ARN (e.g., Titan embeddings)

---

## Boto3 Implementation

### Create Knowledge Base

```python
import boto3

bedrock_agent = boto3.client("bedrock-agent", region_name="us-east-1")

response = bedrock_agent.create_knowledge_base(
    name="my-kb",
    roleArn="YOUR_ROLE_ARN",
    knowledgeBaseConfiguration={
        "type": "VECTOR",
        "vectorKnowledgeBaseConfiguration": {
            "embeddingModelArn": "YOUR_MODEL_ARN"
        },
    },
    storageConfiguration={
        "type": "S3_VECTORS",
        "s3VectorsConfiguration": {
            "vectorBucketArn": "YOUR_VECTOR_BUCKET_ARN",
            "indexName": "YOUR_INDEX_NAME"
        },
    },
)
```

---

### Create Data Source

```python
bedrock_agent.create_data_source(
    knowledgeBaseId="KB_ID",
    name="s3-source",
    dataSourceConfiguration={
        "type": "S3",
        "s3Configuration": {
            "bucketArn": "YOUR_BUCKET_ARN",
            "inclusionPrefixes": ["docs/"]
        },
    },
)
```

---

### Start Ingestion

```python
bedrock_agent.start_ingestion_job(
    knowledgeBaseId="KB_ID",
    dataSourceId="DATA_SOURCE_ID"
)
```

---

## S3 Vectors Setup (Optional)

```python
s3vectors = boto3.client("s3vectors")

s3vectors.create_vector_bucket(
    vectorBucketName="my-vector-bucket"
)

s3vectors.create_index(
    vectorBucketName="my-vector-bucket",
    indexName="my-index",
    dimension=1024,
    distanceMetric="COSINE"
)
```

---

## Terraform Setup

### Required Provider

```hcl
provider "aws" {
  region = "us-east-1"
}
```

---

### S3 Bucket

```hcl
resource "aws_s3_bucket" "kb_source" {
  bucket = "my-kb-source"
}
```

---

### S3 Vectors

```hcl
resource "aws_s3vectors_vector_bucket" "vectors" {
  vector_bucket_name = "my-vector-bucket"
}

resource "aws_s3vectors_index" "index" {
  vector_bucket_name = aws_s3vectors_vector_bucket.vectors.vector_bucket_name
  index_name         = "my-index"
  dimension          = 1024
  distance_metric    = "cosine"
}
```

---

### Knowledge Base

```hcl
resource "aws_bedrockagent_knowledge_base" "kb" {
  name     = "demo-kb"
  role_arn = aws_iam_role.kb_role.arn

  knowledge_base_configuration {
    type = "VECTOR"

    vector_knowledge_base_configuration {
      embedding_model_arn = "MODEL_ARN"
    }
  }

  storage_configuration {
    type = "S3_VECTORS"

    s3vectors_configuration {
      vector_bucket_arn = aws_s3vectors_vector_bucket.vectors.vector_bucket_arn
      index_arn         = aws_s3vectors_index.index.index_arn
    }
  }
}
```

---

## Key Gotchas

- Region must match across all resources
- Embedding dimension must match index dimension
- IAM role must include:
  - S3 read permissions
  - Bedrock invoke permissions
  - S3 Vectors permissions
- Terraform does NOT trigger ingestion automatically

---

## Production Tips

- Add retries + waiters in boto3
- Use KMS encryption where needed
- Use Terraform modules for reuse
- Automate ingestion via CLI or pipeline

---

## Done
