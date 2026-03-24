output "alarm_arns" {
  description = "List of CloudWatch alarm ARNs created by this module"
  value = [
    aws_cloudwatch_metric_alarm.doc_processor_errors.arn,
    aws_cloudwatch_metric_alarm.doc_processor_throttles.arn,
    aws_cloudwatch_metric_alarm.chat_handler_errors.arn,
    aws_cloudwatch_metric_alarm.chat_handler_throttles.arn,
    aws_cloudwatch_metric_alarm.api_5xx.arn,
  ]
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic used for alarm notifications"
  value       = aws_sns_topic.alarms.arn
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}
