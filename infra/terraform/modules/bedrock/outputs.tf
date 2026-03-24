output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  value       = aws_bedrockagent_knowledge_base.main.id
}

output "knowledge_base_arn" {
  description = "Bedrock Knowledge Base ARN"
  value       = aws_bedrockagent_knowledge_base.main.arn
}

output "data_source_id" {
  description = "Bedrock Knowledge Base Data Source ID"
  value       = aws_bedrockagent_data_source.staging.id
}

output "data_source_arn" {
  description = "Bedrock Knowledge Base Data Source ARN"
  value       = aws_bedrockagent_data_source.staging.arn
}
