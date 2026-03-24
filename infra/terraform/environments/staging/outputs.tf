output "ingestion_bucket_name" {
  description = "Name of the document ingestion S3 bucket"
  value       = module.s3.ingestion_bucket_name
}

output "staging_bucket_name" {
  description = "Name of the document staging S3 bucket"
  value       = module.s3.staging_bucket_name
}

output "vectors_bucket_name" {
  description = "Name of the knowledge base vectors S3 bucket"
  value       = module.s3.vectors_bucket_name
}

output "chat_history_table_name" {
  description = "Name of the DynamoDB chat history table"
  value       = module.dynamodb.table_name
}

output "rest_api_url" {
  description = "Base URL for the REST API"
  value       = module.apigw_rest.invoke_url
}

output "websocket_endpoint" {
  description = "WebSocket connection endpoint URL"
  value       = module.apigw_websocket.websocket_endpoint
}

output "document_processor_function_name" {
  description = "Name of the document processor Lambda function"
  value       = module.document_processor_lambda.function_name
}

output "chat_handler_function_name" {
  description = "Name of the chat handler Lambda function"
  value       = module.chat_handler_lambda.function_name
}

output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID (set by provision_bedrock_kb.sh)"
  value       = module.bedrock.knowledge_base_id
}
