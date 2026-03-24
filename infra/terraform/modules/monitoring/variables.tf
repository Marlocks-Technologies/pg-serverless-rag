variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "document_processor_function_name" {
  description = "Name of the document processor Lambda function"
  type        = string
}

variable "chat_handler_function_name" {
  description = "Name of the chat handler Lambda function"
  type        = string
}

variable "rest_api_id" {
  description = "ID of the REST API Gateway"
  type        = string
}

variable "rest_api_stage" {
  description = "Stage name of the deployed REST API"
  type        = string
}

variable "alarm_email" {
  description = "Email address to receive alarm notifications. Leave empty to skip subscription."
  type        = string
  default     = ""
}

variable "error_threshold" {
  description = "Number of Lambda errors in 5 minutes to trigger an alarm"
  type        = number
  default     = 5
}

variable "throttle_threshold" {
  description = "Number of Lambda throttles in 5 minutes to trigger an alarm"
  type        = number
  default     = 10
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
