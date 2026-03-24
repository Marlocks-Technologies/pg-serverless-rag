## Phase 3 Deployment Guide

Complete guide to deploying the RAG Implementation with custom S3 Vectors retrieval.

## Prerequisites

- Phase 2 successfully deployed
  - Document processor Lambda functional
  - Documents processed and vectors stored in S3
  - At least 10-20 documents indexed for testing
- AWS CLI configured
- Terraform 1.6+
- Python 3.11+
- Lambda layer from Phase 2 deployed

## Pre-Deployment Checklist

### 1. Verify Phase 2 Status

```bash
# Check vectors bucket has content
aws s3 ls s3://rag-platform-dev-kb-vectors/vectors/ --recursive | head -10

# Should show vector JSON files like:
# vectors/doc-123_chunk-0.json
# vectors/doc-123_chunk-1.json
```

### 2. Verify Lambda Layer

```bash
# List Lambda layers
aws lambda list-layers --region us-east-1

# Confirm rag-platform-dev-shared layer exists
```

### 3. Update Shared Library (if needed)

If you made changes to shared library components:

```bash
cd services/shared
./package_layer.sh

# Publish new version
aws lambda publish-layer-version \
  --layer-name rag-platform-dev-shared \
  --description "Shared library for RAG Platform (Phase 3)" \
  --zip-file fileb://shared-layer.zip \
  --compatible-runtimes python3.11 python3.12 \
  --region us-east-1

# Note the version number and ARN from output
```

## Deployment Steps

### Step 1: Package Chat Handler

```bash
cd services/chat_handler
./package.sh
```

**Output:**
```
Packaging chat handler Lambda function...
Copying source files...
Creating function zip...
Lambda function package created: chat-handler.zip
Size: 4.5K
```

### Step 2: Update Terraform Variables

Edit `infra/terraform/environments/dev/terraform.tfvars`:

```hcl
# Update if you published new layer version
document_processor_layers = [
  "arn:aws:lambda:us-east-1:123456789012:layer:rag-platform-dev-shared:2"  # New version
]

chat_handler_layers = [
  "arn:aws:lambda:us-east-1:123456789012:layer:rag-platform-dev-shared:2"  # Same layer
]

# Update Lambda package paths
chat_handler_zip = "/absolute/path/to/services/chat_handler/chat-handler.zip"
```

**Or set via command line:**
```bash
export TF_VAR_chat_handler_zip="$(pwd)/services/chat_handler/chat-handler.zip"
```

### Step 3: Review Terraform Changes

```bash
cd infra/terraform/environments/dev

# Initialize if needed
terraform init

# Review changes
terraform plan
```

**Expected changes:**
- Update chat_handler Lambda function code
- Possibly update Lambda layer association
- No infrastructure changes (buckets, APIs already exist)

### Step 4: Deploy

```bash
terraform apply

# Review and confirm
# Type: yes
```

**Deployment time:** ~2-3 minutes

### Step 5: Verify Deployment

```bash
# Get API endpoint
terraform output rest_api_url

# Example: https://abc123def.execute-api.us-east-1.amazonaws.com/dev

# Test health endpoint
curl https://abc123def.execute-api.us-east-1.amazonaws.com/dev/health

# Expected response:
{
  "status": "healthy",
  "service": "chat-handler",
  "version": "0.3.0",
  "phase": "3",
  "features": ["rag", "search", "citations"],
  "requestId": "..."
}
```

### Step 6: Verify Lambda Configuration

```bash
# Check Lambda function
aws lambda get-function \
  --function-name rag-platform-dev-chat-handler \
  --region us-east-1

# Verify environment variables
aws lambda get-function-configuration \
  --function-name rag-platform-dev-chat-handler \
  --region us-east-1 \
  --query 'Environment.Variables'

# Should include:
# - AWS_REGION
# - VECTORS_BUCKET
# - EMBEDDING_MODEL_ID
# - GENERATION_MODEL_ID
# - CHAT_HISTORY_TABLE
```

### Step 7: Run Integration Tests

```bash
cd services/chat_handler/tests

# Run unit tests
pytest test_rag_integration.py -v

# Expected: All tests pass
```

### Step 8: Run End-to-End Tests

```bash
# Set API endpoint
export API_ENDPOINT=$(cd ../../.. && cd infra/terraform/environments/dev && terraform output -raw rest_api_url)

# Run E2E tests
./test_e2e.py
```

**Expected output:**
```
================================================================================
Phase 3 RAG Chat API - End-to-End Tests
================================================================================

API Endpoint: https://abc123.execute-api.us-east-1.amazonaws.com/dev
Region: us-east-1

--------------------------------------------------------------------------------
Testing health check endpoint...
✓ Health check passed

--------------------------------------------------------------------------------
Testing chat query endpoint...
  Query: What is the architecture of the RAG platform?
  ✓ Answer length: 432 chars
  ✓ Citations: 3
  ✓ Chunks retrieved: 3
  ✓ Query intent: factual

  Top citation:
    - Source: architecture.pdf
    - Category: technical-spec
    - Score: 0.89

  Answer preview:
    The RAG platform architecture consists of three main components: document processing, vector storage, and retrieval-augmented generation...

✓ Chat Query PASSED

... [more tests] ...

================================================================================
Test Results: 6 passed, 0 failed
================================================================================
```

## Manual Testing

### Test 1: Simple Question

```bash
curl -X POST $API_ENDPOINT/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What documents are available?",
    "sessionId": "test-1"
  }' | jq .
```

**Expected response structure:**
```json
{
  "success": true,
  "sessionId": "test-1",
  "answer": "Based on the available documents...",
  "citations": [
    {
      "source": "doc1.pdf",
      "documentId": "doc-123",
      "category": "technical-spec",
      "chunkIndex": 0,
      "score": 0.85
    }
  ],
  "metadata": {
    "chunks_retrieved": 5,
    "query_intent": "listing",
    "filters_applied": null
  }
}
```

### Test 2: Filtered Query

```bash
curl -X POST $API_ENDPOINT/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What technical specifications are documented?",
    "sessionId": "test-2",
    "filters": {"category": "technical-spec"},
    "topK": 3
  }' | jq .
```

### Test 3: Document Search

```bash
curl -X POST $API_ENDPOINT/chat/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "deployment architecture",
    "topK": 10
  }' | jq '.results[] | {id, score, text: .text[:100]}'
```

### Test 4: Complex Query

```bash
curl -X POST $API_ENDPOINT/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How does the document processing pipeline work, and what are the key components?",
    "sessionId": "test-3",
    "topK": 7
  }' | jq .
```

## Monitoring Setup

### CloudWatch Dashboard

Create a dashboard to monitor RAG performance:

```bash
# Create dashboard JSON
cat > phase3-dashboard.json << 'EOF'
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum", "label": "Total Queries"}],
          [".", "Errors", {"stat": "Sum", "label": "Errors"}],
          [".", "Duration", {"stat": "Average", "label": "Avg Duration"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Phase 3 RAG Metrics",
        "dimensions": {
          "FunctionName": ["rag-platform-dev-chat-handler"]
        }
      }
    }
  ]
}
EOF

# Create dashboard
aws cloudwatch put-dashboard \
  --dashboard-name RAG-Platform-Phase3 \
  --dashboard-body file://phase3-dashboard.json
```

### CloudWatch Alarms

```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name rag-chat-handler-errors \
  --alarm-description "Alert on high error rate" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=rag-platform-dev-chat-handler \
  --evaluation-periods 1

# High duration alarm (queries taking > 5s)
aws cloudwatch put-metric-alarm \
  --alarm-name rag-chat-handler-slow \
  --alarm-description "Alert on slow queries" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=rag-platform-dev-chat-handler \
  --evaluation-periods 2
```

### Log Insights Queries

**Query latency by component:**
```
fields @timestamp, @message
| filter @message like /processing_query/
| stats count() as queries, avg(duration) as avg_duration by bin(5m)
```

**Top error messages:**
```
fields @timestamp, @message
| filter @type = "ERROR"
| stats count() as error_count by @message
| sort error_count desc
| limit 10
```

**Citation analysis:**
```
fields @timestamp, citations
| filter citations[0].source
| stats count() as queries by citations[0].source
| sort queries desc
```

## Troubleshooting

### Issue: "Service initialization failed"

**Symptoms:** 500 error on all requests, health check fails

**Diagnosis:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/rag-platform-dev-chat-handler --follow

# Look for import errors or missing environment variables
```

**Common causes:**
1. Lambda layer not attached or wrong version
2. Missing environment variables (VECTORS_BUCKET, etc.)
3. Invalid model IDs

**Solution:**
```bash
# Verify layer attachment
aws lambda get-function-configuration \
  --function-name rag-platform-dev-chat-handler \
  --query 'Layers'

# Update environment variables in Terraform and redeploy
```

### Issue: "No vectors found" or empty search results

**Symptoms:** Queries return no citations, answers say "no information available"

**Diagnosis:**
```bash
# Check vectors bucket
aws s3 ls s3://rag-platform-dev-kb-vectors/vectors/ --recursive | wc -l

# Should show > 0 files
```

**Common causes:**
1. Phase 2 not run yet (no documents processed)
2. Wrong bucket name in environment variables
3. IAM permissions issue

**Solution:**
```bash
# Process some documents first
aws s3 cp test-doc.txt s3://rag-platform-dev-doc-ingestion/test-doc.txt

# Wait 1-2 minutes, then check vectors bucket
aws s3 ls s3://rag-platform-dev-kb-vectors/vectors/ --recursive
```

### Issue: Slow query responses (> 5 seconds)

**Symptoms:** Queries timeout or take very long

**Diagnosis:**
```bash
# Check Lambda duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=rag-platform-dev-chat-handler \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum

# Check vector count
aws s3 ls s3://rag-platform-dev-kb-vectors/vectors/ --recursive | wc -l
```

**Common causes:**
1. Too many vectors (> 10k documents = slow S3 list)
2. Cold start (first request is slower)
3. Large context windows

**Solutions:**
1. Increase Lambda memory (improves CPU)
2. Reduce top_k parameter
3. Implement caching (Phase 5)
4. Use provisioned concurrency to avoid cold starts

### Issue: Poor answer quality

**Symptoms:** Answers don't match documents, citations wrong

**Diagnosis:**
```bash
# Test document search directly
curl -X POST $API_ENDPOINT/chat/search \
  -H "Content-Type: application/json" \
  -d '{"query": "your test query", "topK": 10}' | jq '.results'

# Check if relevant chunks are being retrieved
```

**Common causes:**
1. Documents not chunked properly
2. Low similarity scores (increase top_k)
3. Wrong category filters
4. Poor query formulation

**Solutions:**
1. Review chunking parameters (Phase 2)
2. Increase top_k to retrieve more candidates
3. Remove or adjust filters
4. Rephrase queries
5. Add more relevant documents

### Issue: API Gateway errors

**Symptoms:** 403 Forbidden, 502 Bad Gateway, 504 Gateway Timeout

**Diagnosis:**
```bash
# Check API Gateway logs
aws logs tail /aws/apigateway/rag-platform-dev-rest --follow

# Check Lambda permissions
aws lambda get-policy \
  --function-name rag-platform-dev-chat-handler
```

**Common causes:**
1. Lambda permission missing for API Gateway
2. API Gateway timeout (30s limit)
3. CORS issues

**Solutions:**
```bash
# Recreate API Gateway permission
terraform taint module.chat_handler_lambda.aws_lambda_permission.apigateway_invocation
terraform apply

# For timeouts: optimize Lambda or increase timeout (max 30s for API Gateway)
```

## Performance Tuning

### Optimize Lambda Memory

Test different memory settings:

```bash
# Current: 512 MB
# Try: 1024 MB for faster execution

aws lambda update-function-configuration \
  --function-name rag-platform-dev-chat-handler \
  --memory-size 1024

# Test performance, adjust as needed
```

**Memory vs. Cost:**
- 512 MB: Baseline cost, ~3s queries
- 1024 MB: 2x cost, ~2s queries (recommended)
- 2048 MB: 4x cost, ~1.5s queries

### Optimize top_k Parameter

```bash
# Test with different top_k values
for k in 3 5 7 10; do
  echo "Testing top_k=$k"
  time curl -X POST $API_ENDPOINT/chat/query \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"test\", \"topK\": $k}"
done
```

**Recommendations:**
- **top_k=3**: Fast, good for simple questions
- **top_k=5**: Balanced (default)
- **top_k=7-10**: Better quality, slower

### Optimize Filters

Use category filters to reduce search space:

```bash
# Filtered search (faster)
curl -X POST $API_ENDPOINT/chat/query \
  -d '{
    "question": "technical specs",
    "filters": {"category": "technical-spec"}
  }'

# Unfiltered search (slower, broader)
curl -X POST $API_ENDPOINT/chat/query \
  -d '{"question": "technical specs"}'
```

## Cost Monitoring

### Daily Cost Estimate

```bash
# Get invocation count for last 24 hours
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=rag-platform-dev-chat-handler \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum

# Calculate cost (assuming ~$0.003 per query)
# invocations * 0.003 = daily cost
```

### Cost Optimization Tips

1. **Reduce Claude usage**: Lower max_tokens (current: 2000)
2. **Cache results**: Store popular query answers (Phase 5)
3. **Batch queries**: Process multiple questions together
4. **Use Haiku for simple queries**: Switch model based on complexity

## Next Steps

After successful Phase 3 deployment:

1. **Gather usage metrics** (1-2 weeks)
2. **Tune parameters** based on real queries
3. **Add more documents** to knowledge base
4. **Start Phase 4**: WebSocket streaming, conversation history
5. **Plan Phase 5**: Caching, optimization, scaling improvements

## Support Resources

- **CloudWatch Logs**: `/aws/lambda/rag-platform-dev-chat-handler`
- **Documentation**: `docs/PHASE3_COMPLETE.md`
- **Tests**: `services/chat_handler/tests/`
- **Code**: `services/chat_handler/src/handler.py`

## Rollback Procedure

If Phase 3 has issues:

```bash
# Get previous Lambda version
aws lambda list-versions-by-function \
  --function-name rag-platform-dev-chat-handler \
  --max-items 5

# Revert to previous version
aws lambda update-function-code \
  --function-name rag-platform-dev-chat-handler \
  --s3-bucket your-bucket \
  --s3-key previous-version.zip

# Or use Terraform
git checkout HEAD~1 infra/
terraform apply
```

## Success Criteria

✓ Health endpoint returns phase=3
✓ Chat queries return relevant answers
✓ Citations accurate and traceable
✓ Average query latency < 3 seconds
✓ Error rate < 1%
✓ E2E tests passing
✓ No CloudWatch alarms triggered

**Phase 3 deployment complete!** 🎉
