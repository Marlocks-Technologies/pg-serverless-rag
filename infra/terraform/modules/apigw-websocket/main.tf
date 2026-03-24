locals {
  api_name   = "${var.project_name}-${var.environment}-websocket-api"
  stage_name = var.environment
}

# ─── WebSocket API ────────────────────────────────────────────────────────────

resource "aws_apigatewayv2_api" "this" {
  name                       = local.api_name
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"

  tags = merge(var.tags, {
    Name = local.api_name
  })
}

# ─── CloudWatch Log Group for Access Logs ────────────────────────────────────

resource "aws_cloudwatch_log_group" "access_logs" {
  name              = "/aws/apigateway/${local.api_name}/access-logs"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "/aws/apigateway/${local.api_name}/access-logs"
  })
}

# ─── Lambda Integration (shared for all routes) ──────────────────────────────

resource "aws_apigatewayv2_integration" "chat_handler" {
  api_id                    = aws_apigatewayv2_api.this.id
  integration_type          = "AWS_PROXY"
  integration_uri           = var.chat_handler_invoke_arn
  content_handling_strategy = "CONVERT_TO_TEXT"
  passthrough_behavior      = "WHEN_NO_MATCH"
}

# ─── Routes ──────────────────────────────────────────────────────────────────

resource "aws_apigatewayv2_route" "connect" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "$connect"
  target    = "integrations/${aws_apigatewayv2_integration.chat_handler.id}"
}

resource "aws_apigatewayv2_route" "disconnect" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "$disconnect"
  target    = "integrations/${aws_apigatewayv2_integration.chat_handler.id}"
}

resource "aws_apigatewayv2_route" "chat" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "chat"
  target    = "integrations/${aws_apigatewayv2_integration.chat_handler.id}"
}

# ─── Stage ───────────────────────────────────────────────────────────────────

resource "aws_apigatewayv2_stage" "this" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = local.stage_name
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access_logs.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      connectionId     = "$context.connectionId"
      routeKey         = "$context.routeKey"
      status           = "$context.status"
      errorMessage     = "$context.error.message"
      integrationError = "$context.integrationErrorMessage"
    })
  }

  default_route_settings {
    logging_level            = "INFO"
    data_trace_enabled       = false
    detailed_metrics_enabled = true
    throttling_burst_limit   = 100
    throttling_rate_limit    = 50
  }

  tags = merge(var.tags, {
    Name = "${local.api_name}-${local.stage_name}"
  })
}

# ─── Lambda Permissions ───────────────────────────────────────────────────────

resource "aws_lambda_permission" "connect" {
  statement_id  = "AllowWebSocketConnect"
  action        = "lambda:InvokeFunction"
  function_name = var.chat_handler_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

resource "aws_lambda_permission" "disconnect" {
  statement_id  = "AllowWebSocketDisconnect"
  action        = "lambda:InvokeFunction"
  function_name = var.chat_handler_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

resource "aws_lambda_permission" "chat" {
  statement_id  = "AllowWebSocketChat"
  action        = "lambda:InvokeFunction"
  function_name = var.chat_handler_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}
