data "aws_region" "current" {}

locals {
  bedrock_region = var.bedrock_region != "" ? var.bedrock_region : data.aws_region.current.name
  use_kms        = var.kms_key_arn != ""

  # Bedrock model ARN pattern for Haiku across all regions
  haiku_model_arn = "arn:aws:bedrock:${local.bedrock_region}::foundation-model/${var.haiku_model_id}"

  # Knowledge Base ARN (wildcard if not yet known)
  kb_arn = var.knowledge_base_id != "" ? "arn:aws:bedrock:${local.bedrock_region}:${var.aws_account_id}:knowledge-base/${var.knowledge_base_id}" : "arn:aws:bedrock:${local.bedrock_region}:${var.aws_account_id}:knowledge-base/*"
}

# ─── Document Processor Lambda Role ──────────────────────────────────────────

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "document_processor" {
  name               = "${var.project_name}-${var.environment}-document-processor-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-document-processor-role"
  })
}

data "aws_iam_policy_document" "document_processor_policy" {
  # S3 access on ingestion and staging buckets
  statement {
    sid    = "S3BucketAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "${var.ingestion_bucket_arn}/*",
      "${var.staging_bucket_arn}/*",
    ]
  }

  # Textract
  statement {
    sid    = "TextractAccess"
    effect = "Allow"
    actions = [
      "textract:DetectDocumentText",
      "textract:StartDocumentTextDetection",
      "textract:GetDocumentTextDetection",
    ]
    resources = ["*"]
  }

  # Bedrock - invoke Haiku model for classification
  statement {
    sid    = "BedrockInvokeHaiku"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
    ]
    resources = [local.haiku_model_arn]
  }

  # CloudWatch Logs
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      var.document_processor_log_group_arn,
      "${var.document_processor_log_group_arn}:*",
    ]
  }

  # KMS (conditional)
  dynamic "statement" {
    for_each = local.use_kms ? [1] : []
    content {
      sid    = "KMSAccess"
      effect = "Allow"
      actions = [
        "kms:Decrypt",
        "kms:GenerateDataKey",
      ]
      resources = [var.kms_key_arn]
    }
  }
}

resource "aws_iam_role_policy" "document_processor" {
  name   = "${var.project_name}-${var.environment}-document-processor-policy"
  role   = aws_iam_role.document_processor.id
  policy = data.aws_iam_policy_document.document_processor_policy.json
}

# ─── Chat Handler Lambda Role ─────────────────────────────────────────────────

resource "aws_iam_role" "chat_handler" {
  name               = "${var.project_name}-${var.environment}-chat-handler-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-chat-handler-role"
  })
}

data "aws_iam_policy_document" "chat_handler_policy" {
  # DynamoDB for chat history
  statement {
    sid    = "DynamoDBChatHistory"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
    ]
    resources = [
      var.chat_history_table_arn,
      "${var.chat_history_table_arn}/index/*",
    ]
  }

  # Bedrock - retrieve and generate, streaming
  statement {
    sid    = "BedrockInvokeAndRetrieve"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:Retrieve",
      "bedrock:RetrieveAndGenerate",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = [
      "arn:aws:bedrock:${local.bedrock_region}::foundation-model/*",
      local.kb_arn,
    ]
  }

  # S3 read from staging bucket
  statement {
    sid    = "S3StagingRead"
    effect = "Allow"
    actions = [
      "s3:GetObject",
    ]
    resources = ["${var.staging_bucket_arn}/*"]
  }

  # CloudWatch Logs
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      var.chat_handler_log_group_arn,
      "${var.chat_handler_log_group_arn}:*",
    ]
  }

  # API Gateway WebSocket connections management
  statement {
    sid    = "WebSocketManageConnections"
    effect = "Allow"
    actions = [
      "execute-api:ManageConnections",
    ]
    resources = [var.websocket_api_arn]
  }

  # KMS (conditional)
  dynamic "statement" {
    for_each = local.use_kms ? [1] : []
    content {
      sid    = "KMSAccess"
      effect = "Allow"
      actions = [
        "kms:Decrypt",
        "kms:GenerateDataKey",
      ]
      resources = [var.kms_key_arn]
    }
  }
}

resource "aws_iam_role_policy" "chat_handler" {
  name   = "${var.project_name}-${var.environment}-chat-handler-policy"
  role   = aws_iam_role.chat_handler.id
  policy = data.aws_iam_policy_document.chat_handler_policy.json
}

# ─── Bedrock Knowledge Base Service Role ─────────────────────────────────────

data "aws_iam_policy_document" "bedrock_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.aws_account_id]
    }
  }
}

resource "aws_iam_role" "bedrock_kb" {
  name               = "${var.project_name}-${var.environment}-bedrock-kb-role"
  assume_role_policy = data.aws_iam_policy_document.bedrock_trust.json

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-bedrock-kb-role"
  })
}

data "aws_iam_policy_document" "bedrock_kb_policy" {
  # Read from staging and vectors buckets
  statement {
    sid    = "S3BucketRead"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.staging_bucket_arn,
      "${var.staging_bucket_arn}/*",
      var.vectors_bucket_arn,
      "${var.vectors_bucket_arn}/*",
    ]
  }

  # Bedrock model invocation for embeddings
  statement {
    sid    = "BedrockEmbeddings"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
    ]
    resources = ["arn:aws:bedrock:${local.bedrock_region}::foundation-model/*"]
  }

  # S3 Vectors - additional permissions for vector operations
  statement {
    sid    = "S3VectorsAccess"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "${var.vectors_bucket_arn}/*",
    ]
  }

  # KMS (conditional)
  dynamic "statement" {
    for_each = local.use_kms ? [1] : []
    content {
      sid    = "KMSAccess"
      effect = "Allow"
      actions = [
        "kms:Decrypt",
        "kms:GenerateDataKey",
      ]
      resources = [var.kms_key_arn]
    }
  }
}

resource "aws_iam_role_policy" "bedrock_kb" {
  name   = "${var.project_name}-${var.environment}-bedrock-kb-policy"
  role   = aws_iam_role.bedrock_kb.id
  policy = data.aws_iam_policy_document.bedrock_kb_policy.json
}

# ─── EventBridge Role ─────────────────────────────────────────────────────────

data "aws_iam_policy_document" "eventbridge_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eventbridge" {
  name               = "${var.project_name}-${var.environment}-eventbridge-role"
  assume_role_policy = data.aws_iam_policy_document.eventbridge_trust.json

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-eventbridge-role"
  })
}

data "aws_iam_policy_document" "eventbridge_policy" {
  statement {
    sid    = "InvokeLambda"
    effect = "Allow"
    actions = [
      "lambda:InvokeFunction",
    ]
    resources = [
      var.document_processor_lambda_arn,
      var.chat_handler_lambda_arn,
    ]
  }
}

resource "aws_iam_role_policy" "eventbridge" {
  name   = "${var.project_name}-${var.environment}-eventbridge-policy"
  role   = aws_iam_role.eventbridge.id
  policy = data.aws_iam_policy_document.eventbridge_policy.json
}
