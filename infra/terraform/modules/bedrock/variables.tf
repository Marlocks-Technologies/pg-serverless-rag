variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for Bedrock Knowledge Base"
  type        = string
}

variable "staging_bucket_arn" {
  description = "ARN of the document staging S3 bucket (data source)"
  type        = string
}

variable "staging_bucket_name" {
  description = "Name of the document staging S3 bucket"
  type        = string
}

variable "vectors_bucket_arn" {
  description = "ARN of the S3 bucket designated for vector storage (reserved for future S3 Vectors migration)"
  type        = string
}

variable "vectors_bucket_name" {
  description = "Name of the S3 bucket for S3 Vectors storage"
  type        = string
}

variable "bedrock_kb_role_arn" {
  description = "ARN of the IAM role for the Bedrock Knowledge Base"
  type        = string
}

variable "embedding_model_arn" {
  description = "ARN of the Bedrock foundation model used for embeddings"
  type        = string
  default     = "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
}

variable "chunk_size" {
  description = "Target chunk size (tokens) for document splitting in the knowledge base"
  type        = number
  default     = 800
}

variable "chunk_overlap_percentage" {
  description = "Percentage of overlap between adjacent chunks"
  type        = number
  default     = 15
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
