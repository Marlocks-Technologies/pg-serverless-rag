variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "chat_handler_invoke_arn" {
  description = "Invoke ARN of the chat handler Lambda function"
  type        = string
}

variable "chat_handler_function_name" {
  description = "Name of the chat handler Lambda function"
  type        = string
}

variable "log_retention_days" {
  description = "Number of days to retain access log entries"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
