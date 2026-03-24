# Phase 2 Deployment Guide

## Overview

This guide covers deploying and testing the Phase 2 Document Processing Pipeline with full integration of S3 Vectors for embeddings.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.11+ installed
- Terraform 1.6+ installed
- Access to AWS services: S3, Lambda, DynamoDB, Textract, Bedrock

## Architecture Components

Phase 2 implements the complete document processing pipeline:

1. **Document Upload** → S3 Ingestion Bucket triggers Lambda
2. **Multi-Format Parsing** → PDF, DOCX, TXT, CSV, images
3. **OCR** → Amazon Textract for scanned documents
4. **Text Normalization** → Remove control chars, normalize whitespace
5. **LLM Classification** → Claude 3 Haiku categorizes documents
6. **PDF Generation** → ReportLab creates normalized PDF
7. **Staging Upload** → Grouped by category in staging bucket
8. **Metadata Creation** → Stored alongside document
9. **Text Chunking** → 800 tokens with 15% overlap
10. **Embedding Generation** → Titan Embeddings v2 (1536-dim)
11. **Vector Storage** → S3 Vectors with rich metadata

## Deployment Steps

### 1. Package the Shared Library Lambda Layer

```bash
cd services/shared
./package_layer.sh
```

This creates `shared-layer.zip` containing:
- All shared library code (parsers, OCR, text processing, classification)
- Python dependencies (boto3, pypdf, python-docx, Pillow, numpy, reportlab)

Upload to AWS Lambda:

```bash
aws lambda publish-layer-version \
  --layer-name rag-platform-dev-shared \
  --description "Shared library for RAG Platform (Phase 2)" \
  --zip-file fileb://shared-layer.zip \
  --compatible-runtimes python3.11 python3.12 \
  --region us-east-1
```

Note the Layer ARN from the output - you'll need it for Terraform.

### 2. Package the Document Processor Lambda

```bash
cd ../document_processor
./package.sh
```

This creates `document-processor.zip` with the handler code.

### 3. Update Terraform Variables

Edit `infra/terraform/environments/dev/terraform.tfvars`:

```hcl
# Add the Lambda layer ARN
document_processor_layers = [
  "arn:aws:lambda:us-east-1:123456789012:layer:rag-platform-dev-shared:1"
]

# Set Lambda deployment package paths
document_processor_zip = "/path/to/services/document_processor/document-processor.zip"
chat_handler_zip = "/path/to/services/chat_handler/chat-handler.zip"
```

### 4. Deploy Infrastructure

```bash
cd infra/terraform/environments/dev

# Initialize Terraform
terraform init

# Review changes
terraform plan

# Deploy
terraform apply
```

Key resources created:
- Document processor Lambda with Phase 2 handler
- S3 ingestion bucket with Lambda trigger
- S3 staging bucket for processed documents
- S3 vectors bucket for embeddings
- DynamoDB table for metadata
- IAM roles with Bedrock permissions

### 5. Verify Environment Variables

After deployment, verify the Lambda has all required environment variables:

```bash
aws lambda get-function-configuration \
  --function-name rag-platform-dev-document-processor \
  --region us-east-1 \
  --query 'Environment.Variables'
```

Should include:
- `AWS_REGION`
- `INGESTION_BUCKET`
- `STAGING_BUCKET`
- `VECTORS_BUCKET`
- `EMBEDDING_MODEL_ID` (amazon.titan-embed-text-v2:0)
- `HAIKU_MODEL_ID` (anthropic.claude-3-haiku-20240307-v1:0)

## Testing

### Unit Tests

Run the integration tests for individual components:

```bash
cd services/document_processor/tests
pytest test_integration.py -v
```

This tests:
- PDF parsing
- Text parsing
- Text normalization
- Text chunking
- Classification snippet extraction
- Document classification (mocked)
- Supported file types

### End-to-End Test

Run the complete pipeline test:

```bash
cd services/document_processor/tests

# Set environment variables
export PROJECT_NAME=rag-platform
export ENVIRONMENT=dev
export AWS_REGION=us-east-1

# Run test
./test_e2e.py
```

The E2E test:
1. Uploads a technical specification document
2. Waits for processing (up to 60 seconds)
3. Validates metadata in staging bucket
4. Validates processed PDF exists
5. Validates vectors were created in S3
6. Checks vector structure and embedding dimensions

Expected output:
```
Phase 2 End-to-End Integration Test
================================================================================

Step 1: Creating and uploading test document
  ✓ Uploaded: test-documents/test-spec-1234567890.txt
  ✓ Document ID: test-spec-1234567890

Step 2: Waiting for document processing
  ✓ Found metadata file: grouped/technical-spec/test-spec-1234567890.metadata.json

Step 3: Validating metadata
  ✓ documentId: test-spec-1234567890
  ✓ category: technical-spec
  ✓ textLength: 1234
  ✓ chunkCount: 3
  ✓ parserUsed: text

Step 4: Validating processed document
  ✓ Found processed PDF: grouped/technical-spec/test-spec-1234567890.pdf

Step 5: Validating vector storage
  ✓ Found 3 vector files
  ✓ Vector structure valid (embedding dim: 1536)
  ✓ Vector text preview: Technical Specification: RAG Platform Architecture...

================================================================================
✓ END-TO-END TEST PASSED
================================================================================
```

### Manual Test with Sample Document

Upload a sample document manually:

```bash
# Create a test document
cat > test-invoice.txt << 'EOF'
INVOICE

Invoice Number: INV-2024-001
Date: 2024-03-24
Due Date: 2024-04-24

Bill To:
Acme Corporation
123 Main Street
Anytown, ST 12345

Items:
1. Professional Services - $5,000.00
2. Software License - $2,500.00

Subtotal: $7,500.00
Tax (10%): $750.00
Total: $8,250.00

Payment Terms: Net 30 days
EOF

# Upload to ingestion bucket
aws s3 cp test-invoice.txt \
  s3://rag-platform-dev-doc-ingestion/manual-tests/test-invoice.txt
```

Check CloudWatch Logs:

```bash
aws logs tail /aws/lambda/rag-platform-dev-document-processor \
  --follow \
  --region us-east-1
```

Verify the processing output in S3:

```bash
# Check staging bucket for processed document
aws s3 ls s3://rag-platform-dev-doc-staging/grouped/ --recursive

# Check vectors bucket
aws s3 ls s3://rag-platform-dev-kb-vectors/vectors/ --recursive
```

## Monitoring

### CloudWatch Metrics

Key metrics to monitor:
- Lambda invocations
- Lambda errors
- Lambda duration
- S3 event notifications

### CloudWatch Logs

Monitor logs for:
- Document processing status
- Classification results
- Chunking statistics
- Embedding generation
- Vector storage confirmation

Query logs:

```bash
# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/rag-platform-dev-document-processor \
  --filter-pattern "ERROR" \
  --region us-east-1

# Search for specific document
aws logs filter-log-events \
  --log-group-name /aws/lambda/rag-platform-dev-document-processor \
  --filter-pattern "test-spec-1234567890" \
  --region us-east-1
```

## Troubleshooting

### Lambda Timeout

If documents are timing out (300s limit):
1. Check document size and complexity
2. Consider increasing memory (improves CPU allocation)
3. For very large documents, consider async processing

### OCR Failures

If Textract OCR fails:
1. Check IAM permissions for Textract
2. Verify document is in supported format
3. Check document file size (max 10MB for sync, 500MB for async)

### Classification Issues

If document classification returns "unknown":
1. Check Bedrock model permissions
2. Verify Haiku model is available in region
3. Review classification prompt in `document_classifier.py`
4. Check CloudWatch logs for Bedrock API errors

### Vector Storage Errors

If vectors aren't being stored:
1. Check S3 permissions for vectors bucket
2. Verify embedding generation succeeded
3. Check CloudWatch logs for S3 API errors
4. Validate boto3 S3 client configuration

### Missing Dependencies

If Lambda fails with import errors:
1. Verify Lambda layer is attached
2. Check layer ARN in Terraform
3. Rebuild layer with correct Python version
4. Verify all dependencies in requirements.txt

## Performance Optimization

### Lambda Configuration

Current settings:
- **Memory**: 1024 MB (can increase for faster processing)
- **Timeout**: 300 seconds (5 minutes)
- **Runtime**: Python 3.12

Recommendations:
- Increase memory to 2048 MB for documents with OCR
- Monitor duration metrics to optimize

### Cost Optimization

Phase 2 components:
- **Lambda**: ~$0.0000166667 per GB-second
- **Textract**: $1.50 per 1000 pages (OCR)
- **Bedrock Titan Embeddings**: $0.0001 per 1000 input tokens
- **Bedrock Claude Haiku**: $0.00025 per 1000 input tokens
- **S3**: $0.023 per GB storage

Estimated monthly cost for 10,000 documents:
- Lambda execution: ~$5
- OCR (10% require OCR): ~$15
- Embeddings: ~$5
- Classification: ~$2
- S3 storage: ~$5
- **Total: ~$32/month**

## Next Steps

After successful Phase 2 deployment:

1. **Phase 3**: RAG Implementation
   - Custom retrieval using S3 Vectors
   - Query embedding generation
   - Cosine similarity search
   - Result ranking and filtering

2. **Phase 4**: Chat API and Backend
   - REST API for queries
   - WebSocket for streaming responses
   - Session management
   - Citation generation

3. **Phase 5**: Optimization
   - Latency reduction
   - Cost optimization
   - Caching strategies
   - Query performance tuning

## Support

For issues or questions:
- Check CloudWatch Logs for detailed error messages
- Review the implementation files in `services/document_processor/src/`
- Refer to `docs/CUSTOM_RAG_S3_VECTORS.md` for architecture details
- Consult AWS documentation for service-specific issues
