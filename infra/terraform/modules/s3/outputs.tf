output "ingestion_bucket_name" {
  description = "Name of the document ingestion S3 bucket"
  value       = aws_s3_bucket.ingestion.id
}

output "ingestion_bucket_arn" {
  description = "ARN of the document ingestion S3 bucket"
  value       = aws_s3_bucket.ingestion.arn
}

output "staging_bucket_name" {
  description = "Name of the document staging S3 bucket"
  value       = aws_s3_bucket.staging.id
}

output "staging_bucket_arn" {
  description = "ARN of the document staging S3 bucket"
  value       = aws_s3_bucket.staging.arn
}

output "vectors_bucket_name" {
  description = "Name of the knowledge base vectors S3 bucket"
  value       = aws_s3_bucket.vectors.id
}

output "vectors_bucket_arn" {
  description = "ARN of the knowledge base vectors S3 bucket"
  value       = aws_s3_bucket.vectors.arn
}
