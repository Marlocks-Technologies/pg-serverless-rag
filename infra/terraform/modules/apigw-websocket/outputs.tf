output "websocket_api_id" {
  description = "ID of the WebSocket API Gateway"
  value       = aws_apigatewayv2_api.this.id
}

output "websocket_api_arn" {
  description = "ARN of the WebSocket API Gateway"
  value       = aws_apigatewayv2_api.this.arn
}

output "websocket_endpoint" {
  description = "WebSocket connection endpoint URL"
  value       = aws_apigatewayv2_stage.this.invoke_url
}

output "stage_name" {
  description = "Name of the deployed WebSocket stage"
  value       = aws_apigatewayv2_stage.this.name
}

output "execution_arn" {
  description = "Execution ARN of the WebSocket API (used for Lambda permissions and ManageConnections)"
  value       = aws_apigatewayv2_api.this.execution_arn
}
