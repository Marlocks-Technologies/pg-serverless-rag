variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of KMS key for bucket encryption. Leave empty to use AES256."
  type        = string
  default     = ""
}

variable "ingestion_notification_target_arn" {
  description = "ARN of the Lambda function or SQS queue to receive S3 event notifications from the ingestion bucket"
  type        = string
}

variable "ingestion_notification_target_type" {
  description = "Type of the notification target: 'lambda' or 'sqs'"
  type        = string
  default     = "lambda"

  validation {
    condition     = contains(["lambda", "sqs"], var.ingestion_notification_target_type)
    error_message = "ingestion_notification_target_type must be 'lambda' or 'sqs'."
  }
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
