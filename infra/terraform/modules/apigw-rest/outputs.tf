output "rest_api_id" {
  description = "ID of the REST API Gateway"
  value       = aws_api_gateway_rest_api.this.id
}

output "rest_api_arn" {
  description = "ARN of the REST API Gateway"
  value       = aws_api_gateway_rest_api.this.arn
}

output "invoke_url" {
  description = "Invoke URL for the deployed API stage"
  value       = aws_api_gateway_stage.this.invoke_url
}

output "stage_name" {
  description = "Name of the deployed API stage"
  value       = aws_api_gateway_stage.this.stage_name
}

output "execution_arn" {
  description = "Execution ARN of the REST API (used for Lambda permissions)"
  value       = aws_api_gateway_rest_api.this.execution_arn
}
