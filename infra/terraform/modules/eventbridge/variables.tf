variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "staging_bucket_name" {
  description = "Name of the document staging S3 bucket (used in event pattern filter)"
  type        = string
}

variable "sync_trigger_lambda_arn" {
  description = "ARN of the Lambda function to trigger on staging bucket events"
  type        = string
}

variable "sync_trigger_lambda_function_name" {
  description = "Name of the Lambda function to trigger on staging bucket events"
  type        = string
}

variable "event_pattern_prefix" {
  description = "S3 key prefix filter for EventBridge events on the staging bucket"
  type        = string
  default     = "grouped/"
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
