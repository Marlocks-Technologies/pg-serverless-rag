output "rule_name" {
  description = "Name of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.staging_object_created.name
}

output "rule_arn" {
  description = "ARN of the EventBridge rule"
  value       = aws_cloudwatch_event_rule.staging_object_created.arn
}

output "target_id" {
  description = "ID of the EventBridge target"
  value       = aws_cloudwatch_event_target.sync_trigger_lambda.target_id
}
