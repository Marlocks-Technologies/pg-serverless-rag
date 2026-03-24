locals {
  prefix = "${var.project_name}-${var.environment}"
}

# ─── SNS Topic ────────────────────────────────────────────────────────────────

resource "aws_sns_topic" "alarms" {
  name = "${local.prefix}-alarms"

  tags = merge(var.tags, {
    Name = "${local.prefix}-alarms"
  })
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# ─── Lambda Alarms: Document Processor ───────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "doc_processor_errors" {
  alarm_name          = "${local.prefix}-doc-processor-errors"
  alarm_description   = "Document processor Lambda errors exceed ${var.error_threshold} in 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.error_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.document_processor_function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(var.tags, {
    Name = "${local.prefix}-doc-processor-errors"
  })
}

resource "aws_cloudwatch_metric_alarm" "doc_processor_throttles" {
  alarm_name          = "${local.prefix}-doc-processor-throttles"
  alarm_description   = "Document processor Lambda throttles exceed ${var.throttle_threshold} in 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.throttle_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.document_processor_function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(var.tags, {
    Name = "${local.prefix}-doc-processor-throttles"
  })
}

# ─── Lambda Alarms: Chat Handler ─────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "chat_handler_errors" {
  alarm_name          = "${local.prefix}-chat-handler-errors"
  alarm_description   = "Chat handler Lambda errors exceed ${var.error_threshold} in 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.error_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.chat_handler_function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(var.tags, {
    Name = "${local.prefix}-chat-handler-errors"
  })
}

resource "aws_cloudwatch_metric_alarm" "chat_handler_throttles" {
  alarm_name          = "${local.prefix}-chat-handler-throttles"
  alarm_description   = "Chat handler Lambda throttles exceed ${var.throttle_threshold} in 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.throttle_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.chat_handler_function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(var.tags, {
    Name = "${local.prefix}-chat-handler-throttles"
  })
}

# ─── REST API 5xx Alarm ───────────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.prefix}-rest-api-5xx"
  alarm_description   = "REST API 5xx responses exceed 10 in 5 minutes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = "${local.prefix}-rest-api"
    Stage   = var.rest_api_stage
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = merge(var.tags, {
    Name = "${local.prefix}-rest-api-5xx"
  })
}

# ─── CloudWatch Dashboard ─────────────────────────────────────────────────────

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Error Rates"
          region = "us-east-1"
          view   = "timeSeries"
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", var.document_processor_function_name, { label = "DocProcessor Errors", color = "#d62728" }],
            ["AWS/Lambda", "Errors", "FunctionName", var.chat_handler_function_name, { label = "ChatHandler Errors", color = "#ff7f0e" }],
            ["AWS/Lambda", "Throttles", "FunctionName", var.document_processor_function_name, { label = "DocProcessor Throttles", color = "#9467bd" }],
            ["AWS/Lambda", "Throttles", "FunctionName", var.chat_handler_function_name, { label = "ChatHandler Throttles", color = "#8c564b" }],
          ]
          period = 300
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Invocations & Duration"
          region = "us-east-1"
          view   = "timeSeries"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.document_processor_function_name, { label = "DocProcessor Invocations" }],
            ["AWS/Lambda", "Invocations", "FunctionName", var.chat_handler_function_name, { label = "ChatHandler Invocations" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.document_processor_function_name, { label = "DocProcessor Duration (ms)", yAxis = "right" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.chat_handler_function_name, { label = "ChatHandler Duration (ms)", yAxis = "right" }],
          ]
          period = 300
          stat   = "Average"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "API Gateway Latency & Errors"
          region = "us-east-1"
          view   = "timeSeries"
          metrics = [
            ["AWS/ApiGateway", "Latency", "ApiName", "${local.prefix}-rest-api", "Stage", var.rest_api_stage, { label = "REST API Latency p99", stat = "p99" }],
            ["AWS/ApiGateway", "5XXError", "ApiName", "${local.prefix}-rest-api", "Stage", var.rest_api_stage, { label = "REST API 5xx", stat = "Sum", color = "#d62728" }],
            ["AWS/ApiGateway", "4XXError", "ApiName", "${local.prefix}-rest-api", "Stage", var.rest_api_stage, { label = "REST API 4xx", stat = "Sum", color = "#ff7f0e" }],
          ]
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "DynamoDB Consumed Capacity"
          region = "us-east-1"
          view   = "timeSeries"
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "${local.prefix}-chat-history", { label = "Read CU", stat = "Sum" }],
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", "${local.prefix}-chat-history", { label = "Write CU", stat = "Sum" }],
            ["AWS/DynamoDB", "SuccessfulRequestLatency", "TableName", "${local.prefix}-chat-history", "Operation", "Query", { label = "Query Latency (ms)", stat = "Average", yAxis = "right" }],
          ]
          period = 300
        }
      }
    ]
  })
}
