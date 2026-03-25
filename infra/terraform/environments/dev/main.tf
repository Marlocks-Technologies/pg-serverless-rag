terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # backend "s3" {
  #   # Fill in via backend.hcl or -backend-config flags:
  #   #   bucket         = "<your-tf-state-bucket>"
  #   #   key            = "rag/dev/terraform.tfstate"
  #   #   region         = "us-east-1"
  #   #   dynamodb_table = "<your-tf-lock-table>"
  #   #   encrypt        = true
  #   #
  #   # Usage:
  #   #   terraform init -backend-config=backend.hcl
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

locals {
  common_tags = {
    project     = var.project_name
    environment = var.environment
    owner       = "platform-team"
    managed-by  = "terraform"
  }
}

# ─── S3 Buckets ───────────────────────────────────────────────────────────────

module "s3" {
  source = "../../modules/s3"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
  kms_key_arn  = var.kms_key_arn

  # S3 notification will be added separately after Lambda is created
  ingestion_notification_target_arn  = ""
  ingestion_notification_target_type = "lambda"

  tags = local.common_tags
}

# ─── DynamoDB ─────────────────────────────────────────────────────────────────

module "dynamodb" {
  source = "../../modules/dynamodb"

  project_name = var.project_name
  environment  = var.environment
  billing_mode = "PAY_PER_REQUEST"
  kms_key_arn  = var.kms_key_arn
  ttl_enabled  = true

  tags = local.common_tags
}

# WebSocket Connections Table
resource "aws_dynamodb_table" "ws_connections" {
  name         = "${var.project_name}-${var.environment}-ws-connections"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "connectionId"

  attribute {
    name = "connectionId"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-ws-connections"
  })
}

# ─── IAM Roles & Policies ─────────────────────────────────────────────────────

module "iam" {
  source = "../../modules/iam"

  project_name   = var.project_name
  environment    = var.environment
  aws_account_id = var.aws_account_id

  ingestion_bucket_arn   = module.s3.ingestion_bucket_arn
  staging_bucket_arn     = module.s3.staging_bucket_arn
  vectors_bucket_arn     = module.s3.vectors_bucket_arn
  chat_history_table_arn = module.dynamodb.table_arn

  websocket_api_arn   = "${module.apigw_websocket.execution_arn}/*"
  generation_model_id = "eu.amazon.nova-lite-v1:0"
  kms_key_arn         = var.kms_key_arn

  tags = local.common_tags
}

# ─── Shared Lambda Layer ──────────────────────────────────────────────────────

resource "aws_lambda_layer_version" "shared" {
  layer_name          = "${var.project_name}-${var.environment}-shared-layer"
  s3_bucket           = "rag-mt-lambda-layers-${var.aws_account_id}"
  s3_key              = "shared-layer.zip"
  compatible_runtimes = ["python3.12"]

  description = "Shared utilities for RAG platform Lambda functions"
}

# ─── Document Processor Lambda ────────────────────────────────────────────────

module "document_processor_lambda" {
  source = "../../modules/lambda"

  function_name    = "${var.project_name}-${var.environment}-document-processor"
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = var.document_processor_zip
  source_code_hash = filebase64sha256(var.document_processor_zip)
  role_arn         = module.iam.document_processor_role_arn
  memory_size      = 1024
  timeout          = 300
  layers           = [aws_lambda_layer_version.shared.arn]

  environment_variables = {
    AWS_ACCOUNT_ID      = var.aws_account_id
    INGESTION_BUCKET    = "${var.project_name}-${var.environment}-doc-ingestion"
    STAGING_BUCKET      = "${var.project_name}-${var.environment}-doc-staging"
    VECTORS_BUCKET      = "${var.project_name}-${var.environment}-kb-vectors"
    CHAT_HISTORY_TABLE  = "${var.project_name}-${var.environment}-chat-history"
    KNOWLEDGE_BASE_ID   = module.bedrock.knowledge_base_id
    EMBEDDING_MODEL_ID  = "amazon.titan-embed-text-v2:0"
    GENERATION_MODEL_ID = "eu.amazon.nova-lite-v1:0"
    HAIKU_MODEL_ID      = "anthropic.claude-3-haiku-20240307-v1:0"
    LOG_LEVEL           = "INFO"
    ENVIRONMENT         = var.environment
  }

  allow_s3_invocation  = true
  s3_source_bucket_arn = module.s3.ingestion_bucket_arn

  log_retention_days = 30
  tags               = local.common_tags
}

# ─── Chat Handler Lambda ──────────────────────────────────────────────────────

module "chat_handler_lambda" {
  source = "../../modules/lambda"

  function_name    = "${var.project_name}-${var.environment}-chat-handler"
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = var.chat_handler_zip
  source_code_hash = filebase64sha256(var.chat_handler_zip)
  role_arn         = module.iam.chat_handler_role_arn
  memory_size      = 512
  timeout          = 30
  layers           = [aws_lambda_layer_version.shared.arn]

  environment_variables = {
    AWS_ACCOUNT_ID      = var.aws_account_id
    INGESTION_BUCKET    = "${var.project_name}-${var.environment}-doc-ingestion"
    STAGING_BUCKET      = "${var.project_name}-${var.environment}-doc-staging"
    VECTORS_BUCKET      = "${var.project_name}-${var.environment}-kb-vectors"
    CHAT_HISTORY_TABLE  = "${var.project_name}-${var.environment}-chat-history"
    KNOWLEDGE_BASE_ID   = module.bedrock.knowledge_base_id
    EMBEDDING_MODEL_ID  = "amazon.titan-embed-text-v2:0"
    GENERATION_MODEL_ID = "eu.amazon.nova-lite-v1:0"
    HAIKU_MODEL_ID      = "anthropic.claude-3-haiku-20240307-v1:0"
    LOG_LEVEL           = "INFO"
    ENVIRONMENT         = var.environment
  }

  allow_apigateway_invocation = true
  apigateway_source_arn       = "${module.apigw_rest.execution_arn}/*/*"

  log_retention_days = 30
  tags               = local.common_tags
}

# ─── Document Manager Lambda ──────────────────────────────────────────────────

module "document_manager_lambda" {
  source = "../../modules/lambda"

  function_name    = "${var.project_name}-${var.environment}-document-manager"
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = var.document_manager_zip
  source_code_hash = filebase64sha256(var.document_manager_zip)
  role_arn         = module.iam.document_manager_role_arn
  memory_size      = 512
  timeout          = 30
  layers           = [aws_lambda_layer_version.shared.arn]

  environment_variables = {
    AWS_ACCOUNT_ID   = var.aws_account_id
    INGESTION_BUCKET = "${var.project_name}-${var.environment}-doc-ingestion"
    STAGING_BUCKET   = "${var.project_name}-${var.environment}-doc-staging"
    VECTORS_BUCKET   = "${var.project_name}-${var.environment}-kb-vectors"
    DOCUMENTS_TABLE  = "${var.project_name}-${var.environment}-documents"
    LOG_LEVEL        = "INFO"
    ENVIRONMENT      = var.environment
  }

  allow_apigateway_invocation = true
  apigateway_source_arn       = "${module.apigw_rest.execution_arn}/*/*"

  log_retention_days = 30
  tags               = local.common_tags
}

# ─── WebSocket Handler Lambda ─────────────────────────────────────────────────

module "websocket_handler_lambda" {
  source = "../../modules/lambda"

  function_name    = "${var.project_name}-${var.environment}-websocket-handler"
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = var.websocket_handler_zip
  source_code_hash = filebase64sha256(var.websocket_handler_zip)
  role_arn         = module.iam.chat_handler_role_arn # Reuse chat handler role
  memory_size      = 512
  timeout          = 30
  layers           = [aws_lambda_layer_version.shared.arn]

  environment_variables = {
    AWS_ACCOUNT_ID      = var.aws_account_id
    CONNECTIONS_TABLE   = "${var.project_name}-${var.environment}-ws-connections"
    CHAT_HISTORY_TABLE  = "${var.project_name}-${var.environment}-chat-history"
    KNOWLEDGE_BASE_ID   = module.bedrock.knowledge_base_id
    GENERATION_MODEL_ID = "eu.amazon.nova-lite-v1:0"
    LOG_LEVEL           = "INFO"
    ENVIRONMENT         = var.environment
  }

  allow_apigateway_invocation = true
  apigateway_source_arn       = "${module.apigw_websocket.execution_arn}/*"

  log_retention_days = 30
  tags               = local.common_tags
}

# ─── REST API Gateway ─────────────────────────────────────────────────────────

module "apigw_rest" {
  source = "../../modules/apigw-rest"

  project_name                   = var.project_name
  environment                    = var.environment
  chat_handler_invoke_arn        = module.chat_handler_lambda.invoke_arn
  chat_handler_function_name     = module.chat_handler_lambda.function_name
  document_manager_invoke_arn    = module.document_manager_lambda.invoke_arn
  document_manager_function_name = module.document_manager_lambda.function_name
  allowed_origins                = var.allowed_origins
  throttling_burst_limit         = 100
  throttling_rate_limit          = 50
  log_retention_days             = 30

  tags = local.common_tags
}

# ─── WebSocket API Gateway ────────────────────────────────────────────────────

module "apigw_websocket" {
  source = "../../modules/apigw-websocket"

  project_name               = var.project_name
  environment                = var.environment
  chat_handler_invoke_arn    = module.websocket_handler_lambda.invoke_arn
  chat_handler_function_name = module.websocket_handler_lambda.function_name
  log_retention_days         = 30

  tags = local.common_tags
}

# ─── EventBridge ─────────────────────────────────────────────────────────────

module "eventbridge" {
  source = "../../modules/eventbridge"

  project_name                      = var.project_name
  environment                       = var.environment
  staging_bucket_name               = module.s3.staging_bucket_name
  sync_trigger_lambda_arn           = module.document_processor_lambda.function_arn
  sync_trigger_lambda_function_name = module.document_processor_lambda.function_name
  event_pattern_prefix              = "grouped/"

  tags = local.common_tags
}

# ─── Bedrock Knowledge Base (S3 Vectors) ─────────────────────────────────────

module "bedrock" {
  source = "../../modules/bedrock"

  project_name        = var.project_name
  environment         = var.environment
  aws_region          = var.aws_region
  staging_bucket_arn  = module.s3.staging_bucket_arn
  staging_bucket_name = module.s3.staging_bucket_name
  vectors_bucket_arn  = module.s3.vectors_bucket_arn
  vectors_bucket_name = module.s3.vectors_bucket_name
  bedrock_kb_role_arn = module.iam.bedrock_kb_role_arn

  embedding_model_arn      = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
  chunk_size               = 800
  chunk_overlap_percentage = 15

  tags = local.common_tags

  depends_on = [module.iam]
}

# ─── Monitoring ───────────────────────────────────────────────────────────────

module "monitoring" {
  source = "../../modules/monitoring"

  project_name                     = var.project_name
  environment                      = var.environment
  document_processor_function_name = module.document_processor_lambda.function_name
  chat_handler_function_name       = module.chat_handler_lambda.function_name
  rest_api_id                      = module.apigw_rest.rest_api_id
  rest_api_stage                   = module.apigw_rest.stage_name
  alarm_email                      = var.alarm_email
  error_threshold                  = 5
  throttle_threshold               = 10

  tags = local.common_tags
}

# ─── Additional IAM Policies (After Lambda Creation) ──────────────────────────

# EventBridge policy to invoke Lambda functions
data "aws_iam_policy_document" "eventbridge_lambda_policy" {
  statement {
    sid    = "InvokeLambda"
    effect = "Allow"
    actions = [
      "lambda:InvokeFunction",
    ]
    resources = [
      module.document_processor_lambda.function_arn,
      module.chat_handler_lambda.function_arn,
    ]
  }
}

resource "aws_iam_role_policy" "eventbridge_lambda" {
  name   = "${var.project_name}-${var.environment}-eventbridge-lambda-policy"
  role   = module.iam.eventbridge_role_name
  policy = data.aws_iam_policy_document.eventbridge_lambda_policy.json
}

# S3 notification configuration for document processor Lambda
resource "aws_s3_bucket_notification" "ingestion_lambda_trigger" {
  bucket = module.s3.ingestion_bucket_name

  lambda_function {
    lambda_function_arn = module.document_processor_lambda.function_arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
  }
}
