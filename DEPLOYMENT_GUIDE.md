# Deployment Guide - Document Management API

## Overview

This guide covers deploying the Document Management API with the following features:
- Upload documents (PDF, DOCX, TXT, MD) via JSON with base64 encoding
- List documents with filtering by category and status
- Get document details including vector counts
- Delete documents and associated vectors
- Lambda Layer for shared utilities

## Infrastructure Changes

### New Resources

1. **Lambda Layer** (`rag-dev-shared-layer`)
   - Shared utilities for all Lambda functions
   - Includes logging, validation, and S3 helpers
   - Automatically attached to all Lambda functions

2. **Document Manager Lambda** (`rag-dev-document-manager`)
   - Function: `handler.handler`
   - Runtime: Python 3.12
   - Memory: 512 MB
   - Timeout: 30 seconds
   - Layer: shared-layer

3. **IAM Role** (`rag-dev-document-manager-role`)
   - S3 access to ingestion, staging, and vectors buckets
   - DynamoDB access for document metadata
   - CloudWatch Logs permissions

4. **API Gateway Routes**
   - `POST /documents` - Upload document
   - `GET /documents` - List documents with filtering
   - `GET /documents/{documentId}` - Get document details
   - `DELETE /documents/{documentId}` - Delete document
   - CORS enabled for all endpoints

## Prerequisites

Before deployment, ensure you have:

1. **AWS Credentials** configured (`aws configure`)
2. **Terraform** installed (version >= 1.6)
3. **S3 Backend** (optional, for state management)
4. **AWS Account ID** - Update in `terraform.tfvars`

## Deployment Steps

### 1. Package Lambda Functions

```bash
# Package document manager
cd services/document_manager
bash package.sh

# Package shared layer (if not already done)
cd ../shared
bash package_layer.sh

# Package document processor (update existing)
cd ../document_processor
bash package.sh

# Package chat handler (update existing)
cd ../chat_handler
bash package.sh
```

### 2. Configure Terraform Variables

Edit `infra/terraform/environments/dev/terraform.tfvars`:

```hcl
project_name = "rag"
environment  = "dev"
aws_region   = "us-east-1"  # or eu-west-1

# REQUIRED: Fill in your AWS account ID
aws_account_id = "YOUR_AWS_ACCOUNT_ID"

# Optional: KMS encryption
# kms_key_arn = "arn:aws:kms:us-east-1:123456789012:key/..."

# Optional: CloudWatch alarms
# alarm_email = "alerts@example.com"

# CORS origins
allowed_origins = ["*"]  # Use specific domains in production
```

### 3. Initialize Terraform

```bash
cd infra/terraform/environments/dev

# Option A: Without S3 backend (local state)
terraform init -backend=false

# Option B: With S3 backend (recommended)
# Create backend.hcl first:
cat > backend.hcl <<EOF
bucket         = "your-terraform-state-bucket"
key            = "rag/dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-state-lock"
encrypt        = true
EOF

terraform init -backend-config=backend.hcl
```

### 4. Review Terraform Plan

```bash
terraform plan -out=tfplan
```

Expected changes:
- 1 new Lambda Layer
- 1 new Lambda Function (document-manager)
- 1 new IAM Role
- 3 updated Lambda Functions (adding layer)
- 4 new API Gateway resources
- 8 new API Gateway methods
- Multiple integrations and CORS configurations

### 5. Apply Infrastructure Changes

```bash
terraform apply tfplan
```

This will:
1. Create the shared Lambda layer
2. Deploy the document manager Lambda
3. Update existing Lambdas with the layer
4. Configure API Gateway routes
5. Set up IAM permissions

### 6. Verify Deployment

```bash
# Get the API Gateway URL
terraform output rest_api_url

# Example: https://xxxxxxxx.execute-api.us-east-1.amazonaws.com/dev
```

Test the health endpoint:

```bash
curl https://YOUR_API_URL/dev/health
```

Expected response:
```json
{"status": "healthy"}
```

## Testing the Document Management API

### Upload a Document

```bash
# Encode file to base64
FILE_PATH="test-document.pdf"
FILE_BASE64=$(base64 -i "$FILE_PATH")

# Upload via API
curl -X POST https://YOUR_API_URL/dev/documents \
  -H "Content-Type: application/json" \
  -d "{
    \"filename\": \"test-document.pdf\",
    \"content\": \"$FILE_BASE64\",
    \"contentType\": \"application/pdf\",
    \"metadata\": {
      \"author\": \"Test User\",
      \"department\": \"Engineering\"
    }
  }"
```

Expected response (202 Accepted):
```json
{
  "success": true,
  "documentId": "uuid-here",
  "filename": "test-document.pdf",
  "s3Key": "uploads/test-document.pdf",
  "status": "processing",
  "message": "Document uploaded successfully and is being processed"
}
```

### List Documents

```bash
# List all documents
curl https://YOUR_API_URL/dev/documents

# Filter by category
curl "https://YOUR_API_URL/dev/documents?category=technical&limit=10"
```

### Get Document Details

```bash
curl https://YOUR_API_URL/dev/documents/{documentId}
```

### Delete Document

```bash
curl -X DELETE https://YOUR_API_URL/dev/documents/{documentId}
```

## Monitoring

### CloudWatch Logs

View Lambda logs:

```bash
# Document manager logs
aws logs tail /aws/lambda/rag-dev-document-manager --follow

# Document processor logs
aws logs tail /aws/lambda/rag-dev-document-processor --follow

# API Gateway logs
aws logs tail /aws/apigateway/rag-dev-rest-api/access-logs --follow
```

### API Gateway Metrics

Check the AWS Console:
- API Gateway → rag-dev-rest-api → Dashboard
- Monitor: Request count, latency, errors, throttles

## Troubleshooting

### Lambda Layer Issues

If Lambdas can't find shared modules:

```bash
# Rebuild the layer
cd services/shared
rm -rf python
bash package_layer.sh

# Verify layer contents
unzip -l shared-layer.zip | grep -E 'logger|validation|s3_helpers'
```

### Document Upload Fails

Check:
1. File size < 10 MB
2. Supported format (PDF, DOCX, TXT, MD)
3. Content is properly base64-encoded
4. Lambda has S3 permissions

### Document Not Processing

1. Check S3 ingestion bucket for uploaded file
2. Check document processor Lambda logs
3. Verify S3 trigger is configured

### API Gateway 403 Errors

Verify CORS configuration:
```bash
curl -X OPTIONS https://YOUR_API_URL/dev/documents \
  -H "Origin: http://localhost:3000" \
  -v
```

## Rollback

To rollback changes:

```bash
# Revert to previous state
terraform plan -destroy -target=module.document_manager_lambda
terraform apply -destroy -target=module.document_manager_lambda

# Or rollback all new resources
terraform apply -target=module.apigw_rest -destroy
```

## Cost Considerations

Estimated monthly costs (development):
- Lambda invocations: ~$1-5 (1M requests)
- Lambda duration: ~$2-10 (depends on usage)
- API Gateway: ~$3.50 per million requests
- S3 storage: ~$0.023 per GB
- DynamoDB: Pay-per-request (minimal)
- CloudWatch Logs: ~$0.50 per GB ingested

**Total estimate:** $10-30/month for development workload

## Production Considerations

Before deploying to production:

1. **Security**
   - Enable authentication (API keys, Cognito, IAM)
   - Restrict CORS origins
   - Enable KMS encryption
   - Use VPC endpoints for AWS services

2. **Performance**
   - Increase Lambda memory/timeout if needed
   - Configure Lambda reserved concurrency
   - Enable API Gateway caching

3. **Monitoring**
   - Set up CloudWatch alarms
   - Configure SNS notifications
   - Enable X-Ray tracing

4. **Backup**
   - Enable S3 versioning
   - Configure DynamoDB point-in-time recovery
   - Backup Terraform state

## Next Steps

1. Deploy the infrastructure using these instructions
2. Test document upload/management endpoints
3. Implement WebSocket API for streaming responses
4. Configure authentication and authorization
5. Set up CI/CD pipeline for automated deployments

## References

- [DOCUMENT_MANAGEMENT_API.md](./DOCUMENT_MANAGEMENT_API.md) - Complete API documentation
- [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) - Main API documentation
- [WEBSOCKET_STREAMING_API.md](./WEBSOCKET_STREAMING_API.md) - WebSocket API docs
