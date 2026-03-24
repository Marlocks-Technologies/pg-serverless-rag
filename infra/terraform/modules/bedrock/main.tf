# ─── Bedrock Knowledge Base Module ──────────────────────────────────────────
#
# Creates a Bedrock Knowledge Base with Amazon S3 Vectors for storage.
#
# Amazon S3 Vectors provides fully managed vector storage built directly into S3.
# This implementation uses S3 as the exclusive vector storage backend.
#
# References:
#   - https://aws.amazon.com/s3/features/vectors/
#   - https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors.html
#   - https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html
#
# ─────────────────────────────────────────────────────────────────────────────

locals {
  kb_name = "${var.project_name}-${var.environment}-knowledge-base"
  ds_name = "${var.project_name}-${var.environment}-staging-source"

  # SSM parameter names for storing KB identifiers
  ssm_prefix   = "/${var.project_name}/${var.environment}/bedrock"
  kb_id_param  = "${local.ssm_prefix}/knowledge-base-id"
  ds_id_param  = "${local.ssm_prefix}/data-source-id"
  kb_arn_param = "${local.ssm_prefix}/knowledge-base-arn"
}

# ─── Provision Knowledge Base with S3 Vectors via Python Script ──────────────

# S3 Vectors configuration for Bedrock Knowledge Bases
# This uses a Python script with boto3 for provisioning since Terraform support
# for S3 Vectors as a KB backend may still be emerging.

resource "null_resource" "provision_kb_s3_vectors" {
  triggers = {
    staging_bucket  = var.staging_bucket_arn
    vectors_bucket  = var.vectors_bucket_arn
    kb_role         = var.bedrock_kb_role_arn
    embedding_model = var.embedding_model_arn
    project         = var.project_name
    environment     = var.environment
    chunk_size      = var.chunk_size
    chunk_overlap   = var.chunk_overlap_percentage
  }

  provisioner "local-exec" {
    command = <<-EOT
      python3 ${path.module}/../../scripts/provision_bedrock_kb_s3.py \
        --project-name "${var.project_name}" \
        --environment "${var.environment}" \
        --region "${var.aws_region}" \
        --staging-bucket "${var.staging_bucket_name}" \
        --vectors-bucket "${var.vectors_bucket_name}" \
        --kb-role-arn "${var.bedrock_kb_role_arn}" \
        --embedding-model-arn "${var.embedding_model_arn}" \
        --chunk-size ${var.chunk_size} \
        --chunk-overlap-pct ${var.chunk_overlap_percentage}
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = "echo 'Bedrock Knowledge Base will remain active. Delete manually if needed via AWS Console or CLI.'"
  }
}

# ─── Store KB Identifiers in SSM Parameter Store ─────────────────────────────

resource "aws_ssm_parameter" "knowledge_base_id" {
  name        = local.kb_id_param
  type        = "String"
  value       = "PLACEHOLDER"
  description = "Bedrock Knowledge Base ID for ${var.project_name}-${var.environment}. Populated by Python provisioning script."

  lifecycle {
    ignore_changes = [value]
  }

  tags = merge(var.tags, {
    Name = local.kb_id_param
  })

  depends_on = [null_resource.provision_kb_s3_vectors]
}

resource "aws_ssm_parameter" "data_source_id" {
  name        = local.ds_id_param
  type        = "String"
  value       = "PLACEHOLDER"
  description = "Bedrock Knowledge Base Data Source ID for ${var.project_name}-${var.environment}. Populated by Python provisioning script."

  lifecycle {
    ignore_changes = [value]
  }

  tags = merge(var.tags, {
    Name = local.ds_id_param
  })

  depends_on = [null_resource.provision_kb_s3_vectors]
}

resource "aws_ssm_parameter" "knowledge_base_arn" {
  name        = local.kb_arn_param
  type        = "String"
  value       = "PLACEHOLDER"
  description = "Bedrock Knowledge Base ARN for ${var.project_name}-${var.environment}. Populated by Python provisioning script."

  lifecycle {
    ignore_changes = [value]
  }

  tags = merge(var.tags, {
    Name = local.kb_arn_param
  })

  depends_on = [null_resource.provision_kb_s3_vectors]
}

# ─── Read Back KB Identifiers ─────────────────────────────────────────────────

data "aws_ssm_parameter" "knowledge_base_id" {
  name = aws_ssm_parameter.knowledge_base_id.name

  depends_on = [
    null_resource.provision_kb_s3_vectors,
    aws_ssm_parameter.knowledge_base_id
  ]
}

data "aws_ssm_parameter" "data_source_id" {
  name = aws_ssm_parameter.data_source_id.name

  depends_on = [
    null_resource.provision_kb_s3_vectors,
    aws_ssm_parameter.data_source_id
  ]
}

data "aws_ssm_parameter" "knowledge_base_arn" {
  name = aws_ssm_parameter.knowledge_base_arn.name

  depends_on = [
    null_resource.provision_kb_s3_vectors,
    aws_ssm_parameter.knowledge_base_arn
  ]
}
