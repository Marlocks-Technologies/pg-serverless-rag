variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "ingestion_bucket_arn" {
  description = "ARN of the document ingestion S3 bucket"
  type        = string
}

variable "staging_bucket_arn" {
  description = "ARN of the document staging S3 bucket"
  type        = string
}

variable "vectors_bucket_arn" {
  description = "ARN of the S3 bucket for vector storage (S3 Vectors)"
  type        = string
}

variable "chat_history_table_arn" {
  description = "ARN of the DynamoDB chat history table"
  type        = string
}

variable "document_processor_log_group_arn" {
  description = "ARN of the CloudWatch log group for document processor Lambda"
  type        = string
}

variable "chat_handler_log_group_arn" {
  description = "ARN of the CloudWatch log group for chat handler Lambda"
  type        = string
}

variable "bedrock_region" {
  description = "AWS region for Bedrock model invocations"
  type        = string
  default     = ""
}

variable "haiku_model_id" {
  description = "Bedrock model ID for Claude 3 Haiku"
  type        = string
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID (used to scope Bedrock KB IAM actions)"
  type        = string
  default     = ""
}

variable "kms_key_arn" {
  description = "ARN of KMS key. If set, grants kms:Decrypt and kms:GenerateDataKey to Lambda roles."
  type        = string
  default     = ""
}

variable "websocket_api_arn" {
  description = "ARN of the WebSocket API Gateway (for execute-api:ManageConnections)"
  type        = string
  default     = "*"
}

variable "document_processor_lambda_arn" {
  description = "ARN of the document processor Lambda (for EventBridge role)"
  type        = string
  default     = "*"
}

variable "chat_handler_lambda_arn" {
  description = "ARN of the chat handler Lambda (for EventBridge role)"
  type        = string
  default     = "*"
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
