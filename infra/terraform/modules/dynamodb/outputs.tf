output "table_name" {
  description = "Name of the DynamoDB chat history table"
  value       = aws_dynamodb_table.chat_history.name
}

output "table_arn" {
  description = "ARN of the DynamoDB chat history table"
  value       = aws_dynamodb_table.chat_history.arn
}

output "table_id" {
  description = "ID of the DynamoDB chat history table"
  value       = aws_dynamodb_table.chat_history.id
}
