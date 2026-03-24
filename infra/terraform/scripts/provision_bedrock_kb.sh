#!/usr/bin/env bash
# provision_bedrock_kb.sh
# Creates a Bedrock Knowledge Base with S3 Vectors backend and an S3 data source.
# Stores the KB ID and Data Source ID in AWS SSM Parameter Store.
# Idempotent: looks up existing KB by name before creating.
#
# Usage:
#   ./provision_bedrock_kb.sh <env> <region> <staging-bucket> <vectors-bucket> \
#                             <kb-role-arn> <embedding-model-arn>
#
# Example:
#   ./provision_bedrock_kb.sh dev us-east-1 rag-dev-doc-staging rag-dev-kb-vectors \
#     arn:aws:iam::123456789012:role/rag-dev-bedrock-kb-role \
#     arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0

set -euo pipefail

# ─── Arguments ────────────────────────────────────────────────────────────────

if [[ $# -lt 6 ]]; then
  echo "Usage: $0 <env> <region> <staging-bucket> <vectors-bucket> <kb-role-arn> <embedding-model-arn>" >&2
  exit 1
fi

ENV="$1"
REGION="$2"
STAGING_BUCKET="$3"
VECTORS_BUCKET="$4"
KB_ROLE_ARN="$5"
EMBEDDING_MODEL_ARN="$6"

PROJECT_NAME="rag"
KB_NAME="${PROJECT_NAME}-${ENV}-knowledge-base"
DS_NAME="${PROJECT_NAME}-${ENV}-staging-datasource"
SSM_PREFIX="/${PROJECT_NAME}/${ENV}/bedrock"

echo "==> Bedrock Knowledge Base provisioning"
echo "    Environment      : ${ENV}"
echo "    Region           : ${REGION}"
echo "    Staging Bucket   : ${STAGING_BUCKET}"
echo "    Vectors Bucket   : ${VECTORS_BUCKET}"
echo "    KB Role ARN      : ${KB_ROLE_ARN}"
echo "    Embedding Model  : ${EMBEDDING_MODEL_ARN}"
echo "    KB Name          : ${KB_NAME}"
echo "    SSM Prefix       : ${SSM_PREFIX}"

# ─── Check for existing Knowledge Base (idempotent) ──────────────────────────

echo "==> Looking up existing Knowledge Base named '${KB_NAME}'..."

KB_LIST=$(aws bedrock-agent list-knowledge-bases \
  --region "${REGION}" \
  --output json 2>/dev/null || echo '{"knowledgeBaseSummaries":[]}')

KB_ID=$(echo "${KB_LIST}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
summaries = data.get('knowledgeBaseSummaries', [])
for kb in summaries:
    if kb.get('name') == '${KB_NAME}':
        print(kb['knowledgeBaseId'])
        sys.exit(0)
print('')
")

if [[ -n "${KB_ID}" ]]; then
  echo "==> Knowledge Base '${KB_NAME}' already exists with ID: ${KB_ID}"
else
  echo "==> Creating Knowledge Base '${KB_NAME}'..."

  KB_CONFIG=$(cat <<JSON
{
  "type": "VECTOR",
  "vectorKnowledgeBaseConfiguration": {
    "embeddingModelArn": "${EMBEDDING_MODEL_ARN}",
    "embeddingModelConfiguration": {
      "bedrockEmbeddingModelConfiguration": {
        "dimensions": 1536
      }
    }
  }
}
JSON
)

  # S3 Vectors storage configuration
  STORAGE_CONFIG=$(cat <<JSON
{
  "type": "S3_VECTORS",
  "s3VectorsConfiguration": {
    "indexArn": "arn:aws:s3vectors:${REGION}::bucket/${VECTORS_BUCKET}/index/${PROJECT_NAME}-${ENV}-vectors-index"
  }
}
JSON
)

  CREATE_RESPONSE=$(aws bedrock-agent create-knowledge-base \
    --region "${REGION}" \
    --name "${KB_NAME}" \
    --description "RAG Platform Knowledge Base for ${ENV}" \
    --role-arn "${KB_ROLE_ARN}" \
    --knowledge-base-configuration "${KB_CONFIG}" \
    --storage-configuration "${STORAGE_CONFIG}" \
    --output json)

  KB_ID=$(echo "${CREATE_RESPONSE}" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['knowledgeBase']['knowledgeBaseId'])")
  echo "==> Knowledge Base created with ID: ${KB_ID}"

  # Wait for KB to become ACTIVE
  echo "==> Waiting for Knowledge Base to become ACTIVE..."
  for i in $(seq 1 30); do
    STATUS=$(aws bedrock-agent get-knowledge-base \
      --region "${REGION}" \
      --knowledge-base-id "${KB_ID}" \
      --output json | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['knowledgeBase']['status'])")
    echo "    Status: ${STATUS}"
    if [[ "${STATUS}" == "ACTIVE" ]]; then
      break
    fi
    if [[ "${STATUS}" == "FAILED" ]]; then
      echo "ERROR: Knowledge Base creation FAILED." >&2
      exit 1
    fi
    sleep 10
  done
fi

KB_ARN=$(aws bedrock-agent get-knowledge-base \
  --region "${REGION}" \
  --knowledge-base-id "${KB_ID}" \
  --output json | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['knowledgeBase']['knowledgeBaseArn'])")

echo "    Knowledge Base ARN: ${KB_ARN}"

# ─── Check for existing Data Source ──────────────────────────────────────────

echo "==> Looking up existing Data Source named '${DS_NAME}'..."

DS_LIST=$(aws bedrock-agent list-data-sources \
  --region "${REGION}" \
  --knowledge-base-id "${KB_ID}" \
  --output json 2>/dev/null || echo '{"dataSourceSummaries":[]}')

DS_ID=$(echo "${DS_LIST}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
summaries = data.get('dataSourceSummaries', [])
for ds in summaries:
    if ds.get('name') == '${DS_NAME}':
        print(ds['dataSourceId'])
        sys.exit(0)
print('')
")

if [[ -n "${DS_ID}" ]]; then
  echo "==> Data Source '${DS_NAME}' already exists with ID: ${DS_ID}"
else
  echo "==> Creating Data Source '${DS_NAME}'..."

  DS_CONFIG=$(cat <<JSON
{
  "type": "S3",
  "s3Configuration": {
    "bucketArn": "arn:aws:s3:::${STAGING_BUCKET}",
    "inclusionPrefixes": ["grouped/"]
  }
}
JSON
)

  CHUNKING_CONFIG=$(cat <<JSON
{
  "chunkingStrategy": "FIXED_SIZE",
  "fixedSizeChunkingConfiguration": {
    "maxTokens": 800,
    "overlapPercentage": 15
  }
}
JSON
)

  DS_RESPONSE=$(aws bedrock-agent create-data-source \
    --region "${REGION}" \
    --knowledge-base-id "${KB_ID}" \
    --name "${DS_NAME}" \
    --description "Staging bucket data source for ${ENV}" \
    --data-source-configuration "${DS_CONFIG}" \
    --vector-ingestion-configuration "chunkingConfiguration=${CHUNKING_CONFIG}" \
    --output json)

  DS_ID=$(echo "${DS_RESPONSE}" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['dataSource']['dataSourceId'])")
  echo "==> Data Source created with ID: ${DS_ID}"
fi

# ─── Store in SSM Parameter Store ────────────────────────────────────────────

echo "==> Storing KB ID, Data Source ID, and ARN in SSM Parameter Store..."

aws ssm put-parameter \
  --region "${REGION}" \
  --name "${SSM_PREFIX}/knowledge-base-id" \
  --value "${KB_ID}" \
  --type "String" \
  --description "Bedrock Knowledge Base ID for ${PROJECT_NAME}-${ENV}" \
  --overwrite \
  --output json > /dev/null

aws ssm put-parameter \
  --region "${REGION}" \
  --name "${SSM_PREFIX}/data-source-id" \
  --value "${DS_ID}" \
  --type "String" \
  --description "Bedrock Knowledge Base Data Source ID for ${PROJECT_NAME}-${ENV}" \
  --overwrite \
  --output json > /dev/null

aws ssm put-parameter \
  --region "${REGION}" \
  --name "${SSM_PREFIX}/knowledge-base-arn" \
  --value "${KB_ARN}" \
  --type "String" \
  --description "Bedrock Knowledge Base ARN for ${PROJECT_NAME}-${ENV}" \
  --overwrite \
  --output json > /dev/null

echo "==> SSM parameters stored:"
echo "    ${SSM_PREFIX}/knowledge-base-id  = ${KB_ID}"
echo "    ${SSM_PREFIX}/data-source-id     = ${DS_ID}"
echo "    ${SSM_PREFIX}/knowledge-base-arn = ${KB_ARN}"

echo ""
echo "==> Done. Run 'terraform apply' again to pick up the KB ID into Terraform outputs."
echo "    Then update Lambda environment variable KNOWLEDGE_BASE_ID=${KB_ID}"
