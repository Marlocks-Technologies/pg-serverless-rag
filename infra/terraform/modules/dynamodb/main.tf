locals {
  table_name = "${var.project_name}-${var.environment}-chat-history"
  use_kms    = var.kms_key_arn != ""
}

resource "aws_dynamodb_table" "chat_history" {
  name         = local.table_name
  billing_mode = var.billing_mode
  hash_key     = "SessionId"
  range_key    = "Timestamp"

  attribute {
    name = "SessionId"
    type = "S"
  }

  attribute {
    name = "Timestamp"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  dynamic "ttl" {
    for_each = var.ttl_enabled ? [1] : []
    content {
      attribute_name = "ExpiresAt"
      enabled        = true
    }
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = local.use_kms ? var.kms_key_arn : null
  }

  tags = merge(var.tags, {
    Name = local.table_name
  })

  lifecycle {
    prevent_destroy = false
  }
}
