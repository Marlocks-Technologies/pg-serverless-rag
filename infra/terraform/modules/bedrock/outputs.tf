output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  value       = data.aws_ssm_parameter.knowledge_base_id.value
}

output "knowledge_base_arn" {
  description = "Bedrock Knowledge Base ARN"
  value       = data.aws_ssm_parameter.knowledge_base_arn.value
}

output "data_source_id" {
  description = "Bedrock Knowledge Base Data Source ID"
  value       = data.aws_ssm_parameter.data_source_id.value
}

output "data_source_arn" {
  description = "Bedrock Knowledge Base Data Source ARN (placeholder until provisioned)"
  value       = "arn:aws:bedrock:${var.aws_region}:data-source/*"
}

output "ssm_kb_id_parameter" {
  description = "SSM parameter name storing the Knowledge Base ID"
  value       = data.aws_ssm_parameter.knowledge_base_id.name
}

output "ssm_ds_id_parameter" {
  description = "SSM parameter name storing the Data Source ID"
  value       = data.aws_ssm_parameter.data_source_id.name
}
