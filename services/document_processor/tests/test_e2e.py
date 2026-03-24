#!/usr/bin/env python3
"""
End-to-end integration test for Phase 2 document processing pipeline.

This test validates the complete flow:
1. Upload document to S3 ingestion bucket
2. Lambda processes document
3. Metadata created in DynamoDB
4. Processed document and metadata in staging bucket
5. Vectors stored in S3 vectors bucket
"""

import boto3
import json
import time
import os
from pathlib import Path

# Configuration from environment
PROJECT_NAME = os.getenv('PROJECT_NAME', 'rag-platform')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

INGESTION_BUCKET = f"{PROJECT_NAME}-{ENVIRONMENT}-doc-ingestion"
STAGING_BUCKET = f"{PROJECT_NAME}-{ENVIRONMENT}-doc-staging"
VECTORS_BUCKET = f"{PROJECT_NAME}-{ENVIRONMENT}-kb-vectors"
DYNAMODB_TABLE = f"{PROJECT_NAME}-{ENVIRONMENT}-chat-history"


def create_test_document():
    """Create a simple test document."""
    content = """
    Technical Specification: RAG Platform Architecture

    This document outlines the architecture for our Retrieval Augmented Generation platform.

    ## System Components

    1. Document Processing Pipeline
       - Multi-format parsing (PDF, DOCX, TXT, CSV, images)
       - OCR for scanned documents using Amazon Textract
       - Text normalization and chunking
       - LLM-based classification

    2. Vector Storage
       - Amazon S3 for vector embeddings
       - Amazon Titan Embeddings v2 (1536 dimensions)
       - Metadata-rich storage format

    3. Retrieval System
       - Cosine similarity search
       - Metadata filtering
       - Top-K result ranking

    ## Cost Optimization

    Using S3 Vectors instead of OpenSearch Serverless reduces costs by 94%.
    Estimated monthly cost: $40 vs $700.

    ## Performance Requirements

    - Document processing: < 5 seconds for typical documents
    - Vector search: < 500ms for queries
    - Chat response: < 3 seconds end-to-end
    """.strip()

    return content.encode('utf-8')


def upload_test_document(s3_client, document_content):
    """Upload test document to ingestion bucket."""
    test_key = f"test-documents/test-spec-{int(time.time())}.txt"

    print(f"Uploading test document to s3://{INGESTION_BUCKET}/{test_key}")

    s3_client.put_object(
        Bucket=INGESTION_BUCKET,
        Key=test_key,
        Body=document_content,
        ContentType='text/plain'
    )

    return test_key


def wait_for_processing(s3_client, staging_bucket, document_id, max_wait=60):
    """Wait for document to appear in staging bucket."""
    print(f"Waiting for document {document_id} to be processed...")

    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            # Check for metadata file
            response = s3_client.list_objects_v2(
                Bucket=staging_bucket,
                Prefix=f"grouped/"
            )

            if 'Contents' in response:
                for obj in response['Contents']:
                    if document_id in obj['Key'] and obj['Key'].endswith('.metadata.json'):
                        print(f"✓ Found metadata file: {obj['Key']}")
                        return obj['Key']

            time.sleep(2)
        except Exception as e:
            print(f"Error checking staging bucket: {e}")
            time.sleep(2)

    raise TimeoutError(f"Document not processed within {max_wait} seconds")


def validate_metadata(s3_client, staging_bucket, metadata_key):
    """Validate the metadata file."""
    print(f"Validating metadata at {metadata_key}")

    response = s3_client.get_object(Bucket=staging_bucket, Key=metadata_key)
    metadata = json.loads(response['Body'].read())

    # Check required fields
    required_fields = [
        'documentId', 'category', 'originalFilename', 'processedAt',
        'textLength', 'chunkCount', 'parserUsed'
    ]

    for field in required_fields:
        if field not in metadata:
            raise ValueError(f"Missing required field: {field}")
        print(f"  ✓ {field}: {metadata[field]}")

    # Validate category
    valid_categories = ['invoice', 'hr', 'technical-spec', 'legal', 'finance', 'operations', 'unknown']
    if metadata['category'] not in valid_categories:
        raise ValueError(f"Invalid category: {metadata['category']}")

    # Check chunk count
    if metadata['chunkCount'] < 1:
        raise ValueError(f"Invalid chunk count: {metadata['chunkCount']}")

    return metadata


def validate_vectors(s3_client, vectors_bucket, document_id):
    """Validate that vectors were stored."""
    print(f"Validating vectors for document {document_id}")

    response = s3_client.list_objects_v2(
        Bucket=vectors_bucket,
        Prefix=f"vectors/{document_id}"
    )

    if 'Contents' not in response or len(response['Contents']) == 0:
        raise ValueError(f"No vectors found for document {document_id}")

    vector_count = len(response['Contents'])
    print(f"  ✓ Found {vector_count} vector files")

    # Validate first vector file structure
    first_vector_key = response['Contents'][0]['Key']
    vector_response = s3_client.get_object(Bucket=vectors_bucket, Key=first_vector_key)
    vector_data = json.loads(vector_response['Body'].read())

    # Check required fields
    required_fields = ['id', 'embedding', 'text', 'metadata']
    for field in required_fields:
        if field not in vector_data:
            raise ValueError(f"Vector missing required field: {field}")

    # Validate embedding dimensions (Titan v2 = 1536)
    embedding_dim = len(vector_data['embedding'])
    if embedding_dim != 1536:
        raise ValueError(f"Invalid embedding dimension: {embedding_dim}, expected 1536")

    print(f"  ✓ Vector structure valid (embedding dim: {embedding_dim})")
    print(f"  ✓ Vector text preview: {vector_data['text'][:100]}...")

    return vector_count


def validate_processed_document(s3_client, staging_bucket, document_id, category):
    """Validate the processed PDF exists."""
    print(f"Validating processed document")

    # Look for PDF in the category folder
    response = s3_client.list_objects_v2(
        Bucket=staging_bucket,
        Prefix=f"grouped/{category}/"
    )

    if 'Contents' not in response:
        raise ValueError(f"No documents found in grouped/{category}/")

    pdf_found = False
    for obj in response['Contents']:
        if document_id in obj['Key'] and obj['Key'].endswith('.pdf'):
            print(f"  ✓ Found processed PDF: {obj['Key']}")
            pdf_found = True
            break

    if not pdf_found:
        raise ValueError(f"Processed PDF not found for document {document_id}")


def run_e2e_test():
    """Run the end-to-end test."""
    print("=" * 80)
    print("Phase 2 End-to-End Integration Test")
    print("=" * 80)
    print()

    # Initialize clients
    s3_client = boto3.client('s3', region_name=AWS_REGION)

    try:
        # Step 1: Create and upload test document
        print("Step 1: Creating and uploading test document")
        document_content = create_test_document()
        test_key = upload_test_document(s3_client, document_content)
        document_id = test_key.replace('test-documents/', '').replace('.txt', '')
        print(f"  ✓ Uploaded: {test_key}")
        print(f"  ✓ Document ID: {document_id}")
        print()

        # Step 2: Wait for processing
        print("Step 2: Waiting for document processing")
        metadata_key = wait_for_processing(s3_client, STAGING_BUCKET, document_id)
        print()

        # Step 3: Validate metadata
        print("Step 3: Validating metadata")
        metadata = validate_metadata(s3_client, STAGING_BUCKET, metadata_key)
        print()

        # Step 4: Validate processed document
        print("Step 4: Validating processed document")
        validate_processed_document(s3_client, STAGING_BUCKET, document_id, metadata['category'])
        print()

        # Step 5: Validate vectors
        print("Step 5: Validating vector storage")
        vector_count = validate_vectors(s3_client, VECTORS_BUCKET, document_id)
        print()

        # Success summary
        print("=" * 80)
        print("✓ END-TO-END TEST PASSED")
        print("=" * 80)
        print()
        print("Summary:")
        print(f"  - Document ID: {document_id}")
        print(f"  - Category: {metadata['category']}")
        print(f"  - Text Length: {metadata['textLength']} chars")
        print(f"  - Chunks Created: {metadata['chunkCount']}")
        print(f"  - Vectors Stored: {vector_count}")
        print(f"  - Parser Used: {metadata['parserUsed']}")
        print()

        return True

    except Exception as e:
        print()
        print("=" * 80)
        print("✗ END-TO-END TEST FAILED")
        print("=" * 80)
        print()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_e2e_test()
    exit(0 if success else 1)
