variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "rag"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "eu-west-1"
}

variable "aws_account_id" {
  description = "AWS account ID"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of KMS key for encryption. Leave empty to use AES256/AWS-managed keys."
  type        = string
  default     = ""
}

variable "alarm_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
  default     = ""
}

variable "allowed_origins" {
  description = "Allowed CORS origins for the REST API"
  type        = list(string)
  default     = ["*"]
}

variable "document_processor_zip" {
  description = "Path to the document processor Lambda deployment ZIP"
  type        = string
  default     = "../../../../services/document_processor/function.zip"
}

variable "chat_handler_zip" {
  description = "Path to the chat handler Lambda deployment ZIP"
  type        = string
  default     = "../../../../services/chat_handler/function.zip"
}

variable "document_manager_zip" {
  description = "Path to the document manager Lambda deployment ZIP"
  type        = string
  default     = "../../../../services/document_manager/function.zip"
}
