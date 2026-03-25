# RAG Platform Deployment Guide

Complete guide for deploying the Serverless RAG (Retrieval-Augmented Generation) Platform on AWS.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Initial Setup](#initial-setup)
4. [Infrastructure Deployment](#infrastructure-deployment)
5. [Post-Deployment Configuration](#post-deployment-configuration)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)
8. [Cleanup](#cleanup)

---

## Prerequisites

### Required Tools

- **AWS CLI** (v2.0+)
  ```bash
  aws --version
  ```

- **Terraform** (v1.6+)
  ```bash
  terraform version
  ```

- **Python** (3.12+) for Lambda functions
  ```bash
  python3 --version
  ```

- **Git** for version control

### AWS Account Requirements

- AWS account with appropriate permissions
- Programmatic access configured:
  ```bash
  aws configure
  # OR use AWS SSO:
  aws sso login --profile your-profile
  ```

### IAM Permissions Required

Your AWS user/role needs permissions for:
- Lambda (create functions, layers)
- S3 (create buckets, manage objects)
- DynamoDB (create tables)
- API Gateway (create REST and WebSocket APIs)
- IAM (create roles and policies)
- CloudWatch (logs, metrics, alarms)
- Amazon Bedrock (Knowledge Base, models)
- SNS (for alarms)
- SSM Parameter Store

### Bedrock Model Access

Enable access to required models in Amazon Bedrock console:
1. Navigate to Amazon Bedrock console
2. Go to "Model access"
3. Request access to:
   - Claude 3.5 Sonnet (`anthropic.claude-3-5-sonnet-20241022-v2:0`)
   - Claude 3 Haiku (`anthropic.claude-3-haiku-20240307-v1:0`)
   - Titan Embeddings V2 (`amazon.titan-embed-text-v2:0`)

---

## Architecture Overview

### Components

- **S3 Buckets**: Document ingestion, staging, and vector storage
- **Lambda Functions**:
  - Document Processor: Processes uploaded documents
  - Chat Handler: REST API chat endpoint
  - WebSocket Handler: Real-time streaming chat
  - Document Manager: Document CRUD operations
- **API Gateway**:
  - REST API: Document management and synchronous chat
  - WebSocket API: Real-time streaming chat
- **DynamoDB Tables**:
  - Chat History: Conversation persistence
  - WebSocket Connections: Active WebSocket connections
- **Bedrock Knowledge Base**: Vector search and RAG
- **EventBridge**: Triggers for document processing
- **CloudWatch**: Monitoring, logs, and alarms

---

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/rag-platform.git
cd rag-platform
```

### 2. Configure AWS Profile

Set the AWS profile to use:

```bash
export AWS_PROFILE=your-profile-name
```

Verify credentials:

```bash
aws sts get-caller-identity
```

### 3. Prepare Lambda Layer

The shared Lambda layer contains common utilities. Create and upload it:

```bash
cd services/shared_lib
./package_layer.sh
```

This creates `shared-layer.zip` (~55MB). Upload to S3:

```bash
# Create S3 bucket for Lambda layers
aws s3 mb s3://rag-mt-lambda-layers-$(aws sts get-caller-identity --query Account --output text)

# Upload layer
aws s3 cp shared-layer.zip s3://rag-mt-lambda-layers-$(aws sts get-caller-identity --query Account --output text)/shared-layer.zip
```

### 4. Package Lambda Functions

Package each Lambda function:

```bash
# Document Processor
cd services/document_processor
./package.sh

# Chat Handler
cd ../chat_handler
./package.sh

# Document Manager
cd ../document_manager
./package.sh

# WebSocket Handler
cd ../websocket_handler
./package.sh

cd ../..
```

---

## Infrastructure Deployment

### 1. Configure Terraform Variables

Create `terraform.tfvars` in `infra/terraform/environments/dev/`:

```hcl
project_name    = "rag-mt"
environment     = "dev"
aws_region      = "eu-west-1"
aws_account_id  = "YOUR_ACCOUNT_ID"

# Optional
kms_key_arn     = ""  # Leave empty to use AES256
alarm_email     = "alerts@example.com"
allowed_origins = ["*"]  # Restrict in production
```

**Note**: `project_name` must be unique to avoid S3 bucket name conflicts.

### 2. Initialize Terraform

```bash
cd infra/terraform/environments/dev
terraform init
```

### 3. Review Terraform Plan

```bash
terraform plan
```

Review the resources that will be created (~50+ resources).

### 4. Deploy Infrastructure

```bash
terraform apply
```

Type `yes` when prompted. Deployment takes 5-10 minutes.

### 5. Capture Outputs

Save important outputs:

```bash
terraform output -json > outputs.json

# View outputs
terraform output
```

Key outputs:
- `rest_api_url`: REST API endpoint
- `websocket_endpoint`: WebSocket endpoint
- `ingestion_bucket_name`: S3 bucket for document uploads
- `knowledge_base_id`: Bedrock Knowledge Base ID

---

## Post-Deployment Configuration

### 1. Test Document Upload

Upload a test document:

```bash
export AWS_PROFILE=mt-devops

# Create test document
cat > /tmp/test.txt << 'EOF'
Amazon Web Services (AWS) is a comprehensive cloud computing platform.
AWS offers over 200 fully featured services including compute, storage,
databases, analytics, machine learning, and more.
EOF

# Upload to ingestion bucket
aws s3 cp /tmp/test.txt s3://$(terraform output -raw ingestion_bucket_name)/uploads/test.txt
```

### 2. Monitor Processing

Check document processor logs:

```bash
aws logs tail /aws/lambda/$(terraform output -raw document_processor_function_name) --follow
```

The document should be:
1. Downloaded from ingestion bucket
2. Parsed and normalized
3. Converted to PDF
4. Uploaded to staging bucket

Verify in staging bucket:

```bash
aws s3 ls s3://$(terraform output -raw staging_bucket_name)/grouped/ --recursive
```

### 3. Sync Knowledge Base

Trigger Knowledge Base ingestion:

```bash
# Get Knowledge Base details
KB_ID=$(terraform output -raw knowledge_base_id)
DS_ID=$(aws ssm get-parameter --name /rag-mt/dev/bedrock/data-source-id --query 'Parameter.Value' --output text)

# Start ingestion job
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DS_ID \
  --region eu-west-1

# Check status
aws bedrock-agent get-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DS_ID \
  --ingestion-job-id <JOB_ID> \
  --region eu-west-1
```

### 4. Configure Monitoring (Optional)

Update alarm email in terraform.tfvars:

```hcl
alarm_email = "your-email@example.com"
```

Then apply:

```bash
terraform apply
```

Confirm SNS subscription in email.

---

## Verification

### 1. Test REST API

```bash
API_URL=$(terraform output -raw rest_api_url)

# Health check
curl "$API_URL/health"

# Chat query
curl -X POST "$API_URL/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is AWS?",
    "sessionId": "test-session-1"
  }'
```

### 2. Test WebSocket API

Using the Python test client:

```bash
cd tests
pip install -r requirements.txt

# Single query
python3 websocket_test_client.py --question "What is AWS?"

# Full test session
python3 websocket_test_client.py
```

### 3. Test Document Management

```bash
# List documents
curl "$API_URL/documents"

# Get document details
curl "$API_URL/documents/04062d3b-49fe-4fd7-a34e-16dd8e41c8d6"

# Delete document
curl -X DELETE "$API_URL/documents/04062d3b-49fe-4fd7-a34e-16dd8e41c8d6"
```

### 4. Verify CloudWatch Logs

Check logs for each Lambda:

```bash
# Document processor
aws logs tail /aws/lambda/rag-mt-dev-document-processor --since 1h

# Chat handler
aws logs tail /aws/lambda/rag-mt-dev-chat-handler --since 1h

# WebSocket handler
aws logs tail /aws/lambda/rag-mt-dev-websocket-handler --since 1h

# Document manager
aws logs tail /aws/lambda/rag-mt-dev-document-manager --since 1h
```

### 5. Monitor Metrics

Check CloudWatch dashboard:

```bash
# List dashboards
aws cloudwatch list-dashboards

# View dashboard in console
echo "https://console.aws.amazon.com/cloudwatch/home?region=eu-west-1#dashboards:name=rag-mt-dev-dashboard"
```

---

## Troubleshooting

### Lambda Function Errors

**Issue**: Lambda function fails with timeout

**Solution**: Increase timeout in Terraform configuration:

```hcl
timeout = 60  # Increase from 30
```

Apply changes:

```bash
terraform apply
```

### Knowledge Base Ingestion Fails

**Issue**: Documents fail to index

**Possible Causes**:
1. Metadata exceeds 2048 bytes
2. Invalid PDF format
3. S3 bucket permissions

**Solution**: Check ingestion job logs:

```bash
aws bedrock-agent get-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DS_ID \
  --ingestion-job-id <JOB_ID> \
  --region eu-west-1 | jq '.ingestionJob.failureReasons'
```

### API Gateway 403 Forbidden

**Issue**: API requests return 403

**Possible Causes**:
1. CORS not configured correctly
2. Lambda permission missing
3. IAM authentication required but not provided

**Solution**: Check API Gateway configuration and Lambda permissions in Terraform.

### WebSocket Connection Fails

**Issue**: WebSocket connection immediately closes

**Possible Causes**:
1. Wrong endpoint URL
2. Lambda handler error
3. IAM authentication required

**Solution**: Check WebSocket handler logs:

```bash
aws logs tail /aws/lambda/rag-mt-dev-websocket-handler --follow
```

### S3 Bucket Already Exists

**Issue**: Terraform apply fails with "BucketAlreadyExists"

**Solution**: Change `project_name` in terraform.tfvars to make bucket names unique:

```hcl
project_name = "rag-mt-yourname"  # or use a unique suffix
```

---

## Production Deployment

### Additional Considerations

1. **Enable Backend State Locking**

   Uncomment backend configuration in `main.tf`:

   ```hcl
   terraform {
     backend "s3" {
       bucket         = "your-tf-state-bucket"
       key            = "rag/prod/terraform.tfstate"
       region         = "eu-west-1"
       dynamodb_table = "your-tf-lock-table"
       encrypt        = true
     }
   }
   ```

   Initialize:

   ```bash
   terraform init -backend-config=backend.hcl
   ```

2. **Enable KMS Encryption**

   Create KMS key and update terraform.tfvars:

   ```hcl
   kms_key_arn = "arn:aws:kms:eu-west-1:ACCOUNT:key/KEY_ID"
   ```

3. **Restrict CORS Origins**

   ```hcl
   allowed_origins = [
     "https://app.yourdomain.com",
     "https://admin.yourdomain.com"
   ]
   ```

4. **Enable API Gateway Access Logging**

   Configure CloudWatch role ARN in Terraform.

5. **Set Up CI/CD**

   - Use GitHub Actions, GitLab CI, or AWS CodePipeline
   - Automate: build → test → package → deploy
   - Use separate environments (dev, staging, prod)

6. **Implement Authentication**

   - Add Cognito user pool
   - Configure API Gateway authorizers
   - Update Lambda IAM policies

7. **Enable WAF**

   - Add AWS WAF to API Gateway
   - Configure rate limiting
   - Add IP filtering rules

8. **Monitoring and Alerting**

   - Set up CloudWatch alarms for:
     - Lambda errors/throttles
     - API Gateway 4xx/5xx errors
     - DynamoDB throttles
   - Configure SNS topics for alerts
   - Set up dashboards in CloudWatch or third-party tools

---

## Cleanup

To destroy all resources:

```bash
cd infra/terraform/environments/dev

# Preview what will be destroyed
terraform plan -destroy

# Destroy resources
terraform destroy
```

Type `yes` when prompted.

**Manual cleanup required**:
- Lambda layer in S3 bucket (delete bucket manually)
- CloudWatch log groups (retained by default)
- SSM parameters (retained by default)

Delete manually:

```bash
# Delete Lambda layer bucket
aws s3 rb s3://rag-mt-lambda-layers-ACCOUNT_ID --force

# Delete log groups
aws logs describe-log-groups --query 'logGroups[?starts_with(logGroupName, `/aws/lambda/rag-mt-dev`)].logGroupName' --output text | \
  xargs -I {} aws logs delete-log-group --log-group-name {}

# Delete SSM parameters
aws ssm delete-parameter --name /rag-mt/dev/bedrock/knowledge-base-id
aws ssm delete-parameter --name /rag-mt/dev/bedrock/knowledge-base-arn
aws ssm delete-parameter --name /rag-mt/dev/bedrock/data-source-id
```

---

## Cost Optimization

### Expected Monthly Costs (Development)

Assuming moderate usage (~1000 requests/month):

| Service | Estimated Cost |
|---------|----------------|
| Lambda | $5-20 |
| S3 | $5-10 |
| DynamoDB | $2-5 (Pay-per-request) |
| API Gateway | $5-15 |
| Bedrock (Knowledge Base) | $10-30 |
| Bedrock (Model invocations) | $5-50 |
| CloudWatch | $5-10 |
| **Total** | **$37-140/month** |

### Cost Optimization Tips

1. **Use lifecycle policies** on S3 buckets to transition old objects to cheaper storage
2. **Enable DynamoDB autoscaling** or use On-Demand billing
3. **Set Lambda memory appropriately** (don't over-provision)
4. **Use CloudWatch Logs retention** to automatically delete old logs
5. **Monitor and optimize Bedrock usage** (largest variable cost)
6. **Consider Reserved Capacity** for predictable workloads (production)

---

## Security Best Practices

1. **Enable encryption at rest** for all services (use KMS)
2. **Use IAM least privilege** for all roles
3. **Enable CloudTrail** for audit logging
4. **Use VPC endpoints** for internal communication (optional)
5. **Implement API authentication** (Cognito, API keys, or IAM)
6. **Regularly rotate credentials** and API keys
7. **Enable GuardDuty** for threat detection
8. **Use AWS Secrets Manager** for sensitive configuration
9. **Implement input validation** in all Lambda functions
10. **Regular security audits** using AWS Security Hub

---

## Next Steps

- [API Documentation](./API_DOCUMENTATION.md) - REST API reference
- [WebSocket API](./WEBSOCKET_API.md) - WebSocket streaming guide
- [Architecture](./ARCHITECTURE.md) - Detailed architecture diagrams
- [Development Guide](./DEVELOPMENT.md) - Local development setup

---

## Support

For issues or questions:
- Create an issue in the GitHub repository
- Check CloudWatch logs for error details
- Review AWS documentation for specific services

## License

[Your License Here]
