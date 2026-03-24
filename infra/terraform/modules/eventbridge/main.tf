# DEPENDENCY NOTE:
# For EventBridge to receive S3 Object Created events, the staging S3 bucket
# must have EventBridge notifications enabled. In the S3 module, set:
#   aws_s3_bucket_notification.staging { eventbridge = true }
# This is not configured in the S3 module by default because the ingestion bucket
# uses direct Lambda/SQS notifications. If you switch staging to EventBridge-based
# triggers, enable eventbridge = true in the staging bucket notification resource.

locals {
  rule_name = "${var.project_name}-${var.environment}-staging-object-created"
}

# ─── EventBridge Rule ─────────────────────────────────────────────────────────

resource "aws_cloudwatch_event_rule" "staging_object_created" {
  name        = local.rule_name
  description = "Triggers on S3 Object Created events for the staging bucket (prefix: ${var.event_pattern_prefix})"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [var.staging_bucket_name]
      }
      object = {
        key = [{ prefix = var.event_pattern_prefix }]
      }
    }
  })

  tags = merge(var.tags, {
    Name = local.rule_name
  })
}

# ─── EventBridge Target ───────────────────────────────────────────────────────

resource "aws_cloudwatch_event_target" "sync_trigger_lambda" {
  rule      = aws_cloudwatch_event_rule.staging_object_created.name
  target_id = "${var.project_name}-${var.environment}-sync-trigger"
  arn       = var.sync_trigger_lambda_arn
}

# ─── Lambda Permission ────────────────────────────────────────────────────────

resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.sync_trigger_lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.staging_object_created.arn
}
