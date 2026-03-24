#!/usr/bin/env bash
# provision_s3_vectors.sh
# Creates an S3 Vectors index on the specified bucket.
# Idempotent: skips creation if the index already exists.
#
# Usage:
#   ./provision_s3_vectors.sh <bucket-name> <index-name> <region>
#
# Example:
#   ./provision_s3_vectors.sh rag-dev-kb-vectors rag-dev-vectors-index us-east-1

set -euo pipefail

# ─── Arguments ────────────────────────────────────────────────────────────────

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <bucket-name> <index-name> <region>" >&2
  exit 1
fi

BUCKET_NAME="$1"
INDEX_NAME="$2"
REGION="$3"

echo "==> S3 Vectors provisioning"
echo "    Bucket : ${BUCKET_NAME}"
echo "    Index  : ${INDEX_NAME}"
echo "    Region : ${REGION}"

# ─── Check CLI support ────────────────────────────────────────────────────────

# S3 Vectors is a newer AWS service. The 'aws s3vectors' subcommand may not be
# available in older AWS CLI versions. We check and fall back to boto3 if needed.

if aws s3vectors help &>/dev/null 2>&1; then
  echo "==> aws s3vectors CLI subcommand is available"
  USE_CLI=true
else
  echo "==> aws s3vectors CLI subcommand NOT available in this AWS CLI version."
  echo "    Attempting boto3 fallback via Python..."
  USE_CLI=false
fi

# ─── Helper: boto3 fallback ───────────────────────────────────────────────────

create_index_boto3() {
  python3 - <<PYTHON
import sys
import json
import boto3
from botocore.exceptions import ClientError

bucket_name = "${BUCKET_NAME}"
index_name  = "${INDEX_NAME}"
region      = "${REGION}"

# boto3 client for S3 Vectors (service may appear under 's3vectors' or 's3-vectors')
# Adjust the service name if the SDK uses a different identifier.
try:
    client = boto3.client("s3vectors", region_name=region)
except Exception:
    try:
        # Fallback: some SDK versions may use the endpoint directly
        client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=f"https://s3vectors.{region}.amazonaws.com"
        )
    except Exception as e:
        print(f"ERROR: Could not create boto3 client for S3 Vectors: {e}", file=sys.stderr)
        sys.exit(1)

# Check if index already exists
try:
    response = client.get_index(Bucket=bucket_name, IndexName=index_name)
    index_arn = response.get("IndexArn", "unknown")
    print(f"INDEX_ARN={index_arn}")
    print(f"==> Index '{index_name}' already exists. Skipping creation.")
    sys.exit(0)
except ClientError as e:
    if e.response["Error"]["Code"] not in ("NoSuchIndex", "ResourceNotFoundException", "404"):
        print(f"ERROR checking index existence: {e}", file=sys.stderr)
        sys.exit(1)

# Create the index
print(f"==> Creating S3 Vectors index '{index_name}' on bucket '{bucket_name}'...")
try:
    response = client.create_index(
        Bucket=bucket_name,
        IndexName=index_name,
        DataType="float32",
        Dimension=1536,  # titan-embed-text-v2 default dimension
    )
    index_arn = response.get("IndexArn", "unknown")
    print(f"==> Index created successfully.")
    print(f"INDEX_ARN={index_arn}")
except ClientError as e:
    print(f"ERROR: Failed to create index: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON
}

# ─── Main Logic ───────────────────────────────────────────────────────────────

if [[ "${USE_CLI}" == "true" ]]; then
  # Check if the index already exists
  echo "==> Checking if index '${INDEX_NAME}' already exists..."

  EXISTING=$(aws s3vectors get-index \
    --bucket "${BUCKET_NAME}" \
    --index-name "${INDEX_NAME}" \
    --region "${REGION}" \
    --output json 2>/dev/null || echo "NOT_FOUND")

  if [[ "${EXISTING}" != "NOT_FOUND" ]]; then
    INDEX_ARN=$(echo "${EXISTING}" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('IndexArn', 'unknown'))")
    echo "==> Index '${INDEX_NAME}' already exists. Skipping creation."
    echo "INDEX_ARN=${INDEX_ARN}"
    exit 0
  fi

  echo "==> Creating S3 Vectors index '${INDEX_NAME}'..."

  CREATE_RESPONSE=$(aws s3vectors create-index \
    --bucket "${BUCKET_NAME}" \
    --index-name "${INDEX_NAME}" \
    --data-type float32 \
    --dimension 1536 \
    --region "${REGION}" \
    --output json)

  INDEX_ARN=$(echo "${CREATE_RESPONSE}" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('IndexArn', 'unknown'))")
  echo "==> Index created successfully."
  echo "INDEX_ARN=${INDEX_ARN}"
else
  create_index_boto3
fi

echo "==> Done."
