output "document_processor_role_arn" {
  description = "ARN of the IAM role for the document processor Lambda"
  value       = aws_iam_role.document_processor.arn
}

output "chat_handler_role_arn" {
  description = "ARN of the IAM role for the chat handler Lambda"
  value       = aws_iam_role.chat_handler.arn
}

output "bedrock_kb_role_arn" {
  description = "ARN of the IAM service role for Bedrock Knowledge Base"
  value       = aws_iam_role.bedrock_kb.arn
}

output "eventbridge_role_arn" {
  description = "ARN of the IAM role for EventBridge to invoke Lambda functions"
  value       = aws_iam_role.eventbridge.arn
}

output "eventbridge_role_name" {
  description = "Name of the IAM role for EventBridge to invoke Lambda functions"
  value       = aws_iam_role.eventbridge.name
}
