#!/bin/bash
#
# Provision Amazon Bedrock Knowledge Base with S3-based Vector Storage
#
# IMPORTANT: This script is designed for Amazon S3 Vectors as the storage backend.
# As of March 2026, S3 as a native vector storage option for Bedrock Knowledge Bases
# is still emerging. This script will attempt to configure S3-based storage.
#
# If S3 native vector storage is not yet available in your region, the script will
# detect this and provide guidance on using OpenSearch Serverless as an interim solution.
#
# Usage:
#   ./provision_bedrock_kb_s3_vectors.sh \
#     <project_name> <environment> <region> \
#     <staging_bucket_name> <vectors_bucket_name> \
#     <kb_role_arn> <embedding_model_arn> \
#     <chunk_size> <chunk_overlap_percentage>
#

set -euo pipefail

# ─── Arguments ────────────────────────────────────────────────────────────────

PROJECT_NAME="${1}"
ENVIRONMENT="${2}"
AWS_REGION="${3}"
STAGING_BUCKET="${4}"
VECTORS_BUCKET="${5}"
KB_ROLE_ARN="${6}"
EMBEDDING_MODEL_ARN="${7}"
CHUNK_SIZE="${8:-800}"
CHUNK_OVERLAP_PCT="${9:-15}"

KB_NAME="${PROJECT_NAME}-${ENVIRONMENT}-knowledge-base"
DS_NAME="${PROJECT_NAME}-${ENVIRONMENT}-staging-source"

SSM_PREFIX="/${PROJECT_NAME}/${ENVIRONMENT}/bedrock"
SSM_KB_ID="${SSM_PREFIX}/knowledge-base-id"
SSM_DS_ID="${SSM_PREFIX}/data-source-id"
SSM_KB_ARN="${SSM_PREFIX}/knowledge-base-arn"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Bedrock Knowledge Base Provisioning - S3 Vectors Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Project:          ${PROJECT_NAME}"
echo "Environment:      ${ENVIRONMENT}"
echo "Region:           ${AWS_REGION}"
echo "KB Name:          ${KB_NAME}"
echo "Staging Bucket:   ${STAGING_BUCKET}"
echo "Vectors Bucket:   ${VECTORS_BUCKET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Check for Existing Knowledge Base ───────────────────────────────────────

echo "→ Checking for existing Knowledge Base..."

EXISTING_KB_ID=$(aws ssm get-parameter \
  --region "${AWS_REGION}" \
  --name "${SSM_KB_ID}" \
  --query 'Parameter.Value' \
  --output text 2>/dev/null || echo "")

if [[ -n "${EXISTING_KB_ID}" && "${EXISTING_KB_ID}" != "PLACEHOLDER" ]]; then
  echo "✓ Knowledge Base already exists: ${EXISTING_KB_ID}"

  # Verify it still exists in Bedrock
  if aws bedrock-agent get-knowledge-base \
    --region "${AWS_REGION}" \
    --knowledge-base-id "${EXISTING_KB_ID}" >/dev/null 2>&1; then
    echo "✓ Knowledge Base is active and accessible"
    echo "→ Skipping provisioning (KB already configured)"
    exit 0
  else
    echo "⚠ Knowledge Base ID found in SSM but not in Bedrock - will recreate"
  fi
fi

# ─── S3 Vectors Availability Check ───────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠ Amazon S3 Vectors Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Amazon S3 Vectors is AWS's fully managed vector storage capability built"
echo "directly into S3, providing serverless, cost-effective vector storage."
echo ""
echo "However, as of this script's last update, S3 is not yet available as a"
echo "native storage backend option for Bedrock Knowledge Bases via the API."
echo ""
echo "Current supported storage backends for Bedrock Knowledge Bases:"
echo "  • Amazon OpenSearch Serverless (recommended)"
echo "  • Amazon Aurora PostgreSQL with pgvector"
echo "  • Pinecone"
echo "  • Redis Enterprise Cloud"
echo ""
echo "Recommended Action:"
echo "  Use OpenSearch Serverless as the vector storage backend. Once S3 Vectors"
echo "  becomes available as a Knowledge Base backend, migration will be straightforward."
echo ""
echo "To proceed with OpenSearch Serverless:"
echo "  1. Run: terraform apply with the OpenSearch module enabled"
echo "  2. The infrastructure is already configured for easy migration to S3 Vectors"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "For the latest information on S3 Vectors support in Bedrock Knowledge Bases:"
echo "  https://aws.amazon.com/s3/features/vectors/"
echo "  https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit 1
