locals {
  bucket_prefix = "${var.project_name}-${var.environment}"

  ingestion_bucket_name = "${local.bucket_prefix}-doc-ingestion"
  staging_bucket_name   = "${local.bucket_prefix}-doc-staging"
  vectors_bucket_name   = "${local.bucket_prefix}-kb-vectors"

  use_kms = var.kms_key_arn != ""
}

# ─── Ingestion Bucket ────────────────────────────────────────────────────────

resource "aws_s3_bucket" "ingestion" {
  bucket = local.ingestion_bucket_name

  tags = merge(var.tags, {
    Name = local.ingestion_bucket_name
  })
}

resource "aws_s3_bucket_versioning" "ingestion" {
  bucket = aws_s3_bucket.ingestion.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ingestion" {
  bucket = aws_s3_bucket.ingestion.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = local.use_kms ? "aws:kms" : "AES256"
      kms_master_key_id = local.use_kms ? var.kms_key_arn : null
    }
    bucket_key_enabled = local.use_kms
  }
}

resource "aws_s3_bucket_public_access_block" "ingestion" {
  bucket = aws_s3_bucket.ingestion.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "ingestion" {
  bucket = aws_s3_bucket.ingestion.id

  rule {
    id     = "expire-objects-90-days"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_notification" "ingestion" {
  bucket      = aws_s3_bucket.ingestion.id
  eventbridge = false

  dynamic "lambda_function" {
    for_each = var.ingestion_notification_target_type == "lambda" ? [1] : []
    content {
      lambda_function_arn = var.ingestion_notification_target_arn
      events              = ["s3:ObjectCreated:*"]
    }
  }

  dynamic "queue" {
    for_each = var.ingestion_notification_target_type == "sqs" ? [1] : []
    content {
      queue_arn = var.ingestion_notification_target_arn
      events    = ["s3:ObjectCreated:*"]
    }
  }
}

# ─── Staging Bucket ──────────────────────────────────────────────────────────

resource "aws_s3_bucket" "staging" {
  bucket = local.staging_bucket_name

  tags = merge(var.tags, {
    Name = local.staging_bucket_name
  })
}

resource "aws_s3_bucket_versioning" "staging" {
  bucket = aws_s3_bucket.staging.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "staging" {
  bucket = aws_s3_bucket.staging.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = local.use_kms ? "aws:kms" : "AES256"
      kms_master_key_id = local.use_kms ? var.kms_key_arn : null
    }
    bucket_key_enabled = local.use_kms
  }
}

resource "aws_s3_bucket_public_access_block" "staging" {
  bucket = aws_s3_bucket.staging.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "staging" {
  bucket = aws_s3_bucket.staging.id

  rule {
    id     = "transition-to-standard-ia"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 60
    }
  }
}

# ─── Knowledge Base / Vectors Bucket ─────────────────────────────────────────

resource "aws_s3_bucket" "vectors" {
  bucket = local.vectors_bucket_name

  tags = merge(var.tags, {
    Name = local.vectors_bucket_name
  })
}

resource "aws_s3_bucket_versioning" "vectors" {
  bucket = aws_s3_bucket.vectors.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "vectors" {
  bucket = aws_s3_bucket.vectors.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = local.use_kms ? "aws:kms" : "AES256"
      kms_master_key_id = local.use_kms ? var.kms_key_arn : null
    }
    bucket_key_enabled = local.use_kms
  }
}

resource "aws_s3_bucket_public_access_block" "vectors" {
  bucket = aws_s3_bucket.vectors.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
