variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "handler" {
  description = "Lambda function handler (e.g. handler.handler)"
  type        = string
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.12"
}

variable "filename" {
  description = "Path to the Lambda deployment ZIP package"
  type        = string
}

variable "source_code_hash" {
  description = "Base64-encoded SHA256 hash of the deployment package"
  type        = string
}

variable "role_arn" {
  description = "ARN of the IAM role for the Lambda function"
  type        = string
}

variable "memory_size" {
  description = "Amount of memory (MB) to allocate to the Lambda function"
  type        = number
  default     = 512
}

variable "timeout" {
  description = "Maximum execution time in seconds for the Lambda function"
  type        = number
  default     = 300
}

variable "environment_variables" {
  description = "Environment variables to set on the Lambda function"
  type        = map(string)
  default     = {}
}

variable "reserved_concurrent_executions" {
  description = "Reserved concurrency for this Lambda function. -1 means unreserved."
  type        = number
  default     = -1
}

variable "layers" {
  description = "List of Lambda layer ARNs to attach"
  type        = list(string)
  default     = []
}

variable "vpc_config" {
  description = "VPC configuration for the Lambda function"
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "allow_s3_invocation" {
  description = "Whether to allow S3 to invoke this Lambda function"
  type        = bool
  default     = false
}

variable "s3_source_bucket_arn" {
  description = "ARN of the S3 bucket allowed to invoke this Lambda (required if allow_s3_invocation = true)"
  type        = string
  default     = ""
}

variable "allow_apigateway_invocation" {
  description = "Whether to allow API Gateway to invoke this Lambda function"
  type        = bool
  default     = false
}

variable "apigateway_source_arn" {
  description = "Source ARN for API Gateway invocation permission (required if allow_apigateway_invocation = true)"
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch log entries"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
