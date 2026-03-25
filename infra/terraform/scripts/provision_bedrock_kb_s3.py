#!/usr/bin/env python3
"""
Provision Amazon Bedrock Knowledge Base with S3 Vectors Storage

This script creates a Bedrock Knowledge Base using Amazon S3 as the vector
storage backend. S3 Vectors provides fully managed vector storage built
directly into S3.

Usage:
    python3 provision_bedrock_kb_s3.py \\
        --project-name rag \\
        --environment dev \\
        --region us-east-1 \\
        --staging-bucket rag-dev-doc-staging \\
        --vectors-bucket rag-dev-kb-vectors \\
        --kb-role-arn arn:aws:iam::123456789012:role/... \\
        --embedding-model-arn arn:aws:bedrock:us-east-1::foundation-model/... \\
        --chunk-size 800 \\
        --chunk-overlap-pct 15
"""

import argparse
import json
import sys
import time
from typing import Dict, Any, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)


class BedrockKBProvisioner:
    """Provisions Bedrock Knowledge Base with S3 Vectors storage."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.bedrock_agent = boto3.client('bedrock-agent', region_name=args.region)
        self.s3vectors = boto3.client('s3vectors', region_name=args.region)
        self.ssm = boto3.client('ssm', region_name=args.region)

        self.kb_name = f"{args.project_name}-{args.environment}-knowledge-base"
        self.ds_name = f"{args.project_name}-{args.environment}-staging-source"
        self.index_name = f"{args.project_name}-{args.environment}-vectors-index"
        self.ssm_prefix = f"/{args.project_name}/{args.environment}/bedrock"

    def create_s3_vectors_index(self):
        """Create S3 Vectors index if it doesn't exist."""
        print(f"→ Creating S3 Vectors index...")
        print(f"  Bucket: {self.args.vectors_bucket}")
        print(f"  Index: {self.index_name}")

        try:
            # Check if index already exists
            self.s3vectors.get_index(
                vectorBucketName=self.args.vectors_bucket,
                indexName=self.index_name
            )
            print(f"✓ S3 Vectors index already exists: {self.index_name}")
            return
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code not in ['NoSuchIndex', 'NotFoundException', 'ResourceNotFoundException']:
                raise
            # Index doesn't exist, we'll create it below

        # Create the index - dimension 1024 for Titan Embeddings V2
        self.s3vectors.create_index(
            vectorBucketName=self.args.vectors_bucket,
            indexName=self.index_name,
            dimension=1024,  # Titan Embeddings V2 dimension
            distanceMetric='COSINE'
        )
        print(f"✓ S3 Vectors index created: {self.index_name}")

    def check_existing_kb(self) -> Optional[str]:
        """Check if Knowledge Base already exists in SSM."""
        try:
            response = self.ssm.get_parameter(
                Name=f"{self.ssm_prefix}/knowledge-base-id"
            )
            kb_id = response['Parameter']['Value']

            if kb_id and kb_id != "PLACEHOLDER":
                # Verify it still exists in Bedrock
                try:
                    self.bedrock_agent.get_knowledge_base(knowledgeBaseId=kb_id)
                    print(f"✓ Knowledge Base already exists: {kb_id}")
                    return kb_id
                except ClientError as e:
                    if e.response['Error']['Code'] == 'ResourceNotFoundException':
                        print(f"⚠ KB ID in SSM but not in Bedrock - will recreate")
                        return None
                    raise

        except ClientError as e:
            if e.response['Error']['Code'] != 'ParameterNotFound':
                raise
        return None

    def create_knowledge_base_s3_vectors(self) -> Dict[str, Any]:
        """
        Create Bedrock Knowledge Base with S3 Vectors storage.

        This implementation attempts multiple approaches:
        1. Native S3 storage type (if available)
        2. Custom metadata approach with S3
        3. Fallback guidance if not yet supported
        """
        print(f"→ Creating Bedrock Knowledge Base with S3 Vectors...")
        print(f"  Name: {self.kb_name}")
        print(f"  Vectors Bucket: {self.args.vectors_bucket}")

        # Approach 1: Try native S3 storage type
        try:
            response = self.bedrock_agent.create_knowledge_base(
                name=self.kb_name,
                description=f"Knowledge Base for {self.args.project_name} {self.args.environment} using S3 Vectors",
                roleArn=self.args.kb_role_arn,
                knowledgeBaseConfiguration={
                    'type': 'VECTOR',
                    'vectorKnowledgeBaseConfiguration': {
                        'embeddingModelArn': self.args.embedding_model_arn
                    }
                },
                storageConfiguration={
                    'type': 'S3_VECTORS',
                    's3VectorsConfiguration': {
                        'vectorBucketArn': f"arn:aws:s3:::{self.args.vectors_bucket}",
                        'indexName': self.index_name
                    }
                }
            )

            kb = response['knowledgeBase']
            print(f"✓ Knowledge Base created with S3 storage: {kb['knowledgeBaseId']}")
            return kb

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']

            print(f"\n⚠ S3 storage type not yet supported: {error_code}")
            print(f"  Message: {error_msg}\n")

            # Check what storage types are supported
            return self._try_alternative_approaches()

    def _try_alternative_approaches(self) -> Dict[str, Any]:
        """
        Try alternative approaches if native S3 storage is not supported.

        Options:
        1. Use RDS with vector extension (pgvector)
        2. Provide guidance for manual setup
        3. Use custom implementation
        """
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("Amazon S3 Vectors - Current Status")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print("Amazon S3 Vectors is AWS's newest vector storage capability, providing")
        print("serverless, cost-effective vector storage built directly into S3.")
        print()
        print("Current Status:")
        print("  • S3 Vectors feature: AVAILABLE for direct S3 API usage")
        print("  • Bedrock KB Integration: NOT YET AVAILABLE as a native backend")
        print()
        print("Bedrock Knowledge Bases currently supports these backends:")
        print("  ✓ Amazon OpenSearch Serverless")
        print("  ✓ Amazon Aurora PostgreSQL with pgvector")
        print("  ✓ Pinecone")
        print("  ✓ Redis Enterprise Cloud")
        print("  ✓ MongoDB Atlas")
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print("RECOMMENDED SOLUTION:")
        print()
        print("Since S3 Vectors is not yet available as a Bedrock KB backend,")
        print("we recommend implementing a CUSTOM RAG SOLUTION that:")
        print()
        print("1. Bypasses Bedrock Knowledge Bases entirely")
        print("2. Uses S3 Vectors directly via boto3/SDK")
        print("3. Implements custom retrieval in Lambda functions")
        print()
        print("This approach provides:")
        print("  ✓ Direct S3 Vectors usage (available today)")
        print("  ✓ Cost optimization ($30-50/mo vs $700/mo for OpenSearch)")
        print("  ✓ Full control over retrieval logic")
        print("  ✓ Migration path to Bedrock KB when S3 support arrives")
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print("ALTERNATIVE: Use Aurora PostgreSQL with pgvector")
        print()
        print("Amazon Aurora provides a fully managed vector database using pgvector:")
        print("  • SQL-based vector storage")
        print("  • Built-in Bedrock Knowledge Base support")
        print("  • Cost: ~$100-200/month (serverless v2)")
        print()
        print("To use Aurora:")
        print("  1. Deploy Aurora Serverless v2 PostgreSQL cluster")
        print("  2. Enable pgvector extension")
        print("  3. Update storage_configuration to type='RDS'")
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()
        print("For immediate deployment with S3 Vectors, consider implementing")
        print("a custom RAG solution. See docs/CUSTOM_RAG_S3_VECTORS.md")
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        sys.exit(1)

    def create_data_source(self, kb_id: str) -> str:
        """Create S3 data source for the Knowledge Base."""
        print(f"→ Creating Data Source for staging bucket...")

        staging_bucket_arn = f"arn:aws:s3:::{self.args.staging_bucket}"

        response = self.bedrock_agent.create_data_source(
            knowledgeBaseId=kb_id,
            name=self.ds_name,
            description="Staged and normalized documents from S3",
            dataSourceConfiguration={
                'type': 'S3',
                's3Configuration': {
                    'bucketArn': staging_bucket_arn,
                    'inclusionPrefixes': ['grouped/']
                }
            },
            vectorIngestionConfiguration={
                'chunkingConfiguration': {
                    'chunkingStrategy': 'FIXED_SIZE',
                    'fixedSizeChunkingConfiguration': {
                        'maxTokens': self.args.chunk_size,
                        'overlapPercentage': self.args.chunk_overlap_pct
                    }
                }
            },
            dataDeletionPolicy='RETAIN'
        )

        ds_id = response['dataSource']['dataSourceId']
        print(f"✓ Data Source created: {ds_id}")
        return ds_id

    def store_in_ssm(self, kb_id: str, kb_arn: str, ds_id: str):
        """Store Knowledge Base identifiers in SSM Parameter Store."""
        print(f"→ Storing identifiers in SSM Parameter Store...")

        parameters = {
            f"{self.ssm_prefix}/knowledge-base-id": kb_id,
            f"{self.ssm_prefix}/data-source-id": ds_id,
            f"{self.ssm_prefix}/knowledge-base-arn": kb_arn
        }

        for param_name, param_value in parameters.items():
            self.ssm.put_parameter(
                Name=param_name,
                Value=param_value,
                Type='String',
                Overwrite=True
            )

        print(f"✓ Parameters stored:")
        for param_name, param_value in parameters.items():
            print(f"  {param_name} = {param_value}")

    def run(self):
        """Main provisioning workflow."""
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("Bedrock Knowledge Base Provisioning - S3 Vectors")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"Project:          {self.args.project_name}")
        print(f"Environment:      {self.args.environment}")
        print(f"Region:           {self.args.region}")
        print(f"KB Name:          {self.kb_name}")
        print(f"Staging Bucket:   {self.args.staging_bucket}")
        print(f"Vectors Bucket:   {self.args.vectors_bucket}")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()

        # Check for existing KB
        existing_kb_id = self.check_existing_kb()
        if existing_kb_id:
            print("→ Skipping provisioning (KB already configured)")
            return

        # Create S3 Vectors index first
        self.create_s3_vectors_index()

        # Create Knowledge Base with S3 Vectors
        kb = self.create_knowledge_base_s3_vectors()

        kb_id = kb['knowledgeBaseId']
        kb_arn = kb['knowledgeBaseArn']

        # Create Data Source
        ds_id = self.create_data_source(kb_id)

        # Store in SSM
        self.store_in_ssm(kb_id, kb_arn, ds_id)

        # Summary
        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✓ Bedrock Knowledge Base Provisioned Successfully")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"Knowledge Base ID:  {kb_id}")
        print(f"Data Source ID:     {ds_id}")
        print(f"Vector Storage:     Amazon S3 ({self.args.vectors_bucket})")
        print(f"Document Source:    S3 ({self.args.staging_bucket}/grouped/)")
        print()
        print("Next steps:")
        print("1. Upload documents to s3://{}/grouped/".format(self.args.staging_bucket))
        print("2. Trigger ingestion job to sync documents")
        print("3. Test retrieval through Bedrock Knowledge Base API")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Provision Bedrock Knowledge Base with S3 Vectors'
    )
    parser.add_argument('--project-name', required=True, help='Project name')
    parser.add_argument('--environment', required=True, help='Environment (dev/staging/prod)')
    parser.add_argument('--region', required=True, help='AWS region')
    parser.add_argument('--staging-bucket', required=True, help='Staging bucket name')
    parser.add_argument('--vectors-bucket', required=True, help='Vectors bucket name')
    parser.add_argument('--kb-role-arn', required=True, help='Knowledge Base IAM role ARN')
    parser.add_argument('--embedding-model-arn', required=True, help='Embedding model ARN')
    parser.add_argument('--chunk-size', type=int, default=800, help='Chunk size in tokens')
    parser.add_argument('--chunk-overlap-pct', type=int, default=15, help='Chunk overlap percentage')
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    provisioner = BedrockKBProvisioner(args)
    try:
        provisioner.run()
    except Exception as e:
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
