locals {
  api_name    = "${var.project_name}-${var.environment}-rest-api"
  stage_name  = var.environment
  cors_origin = join(",", var.allowed_origins)
}

# ─── REST API ─────────────────────────────────────────────────────────────────

resource "aws_api_gateway_rest_api" "this" {
  name        = local.api_name
  description = "RAG Platform REST API - ${var.environment}"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(var.tags, {
    Name = local.api_name
  })
}

# Ensure API Gateway generated error responses (4XX/5XX) include CORS headers.
# This prevents browser-side CORS failures when requests fail before Lambda returns.
resource "aws_api_gateway_gateway_response" "default_4xx" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  response_type = "DEFAULT_4XX"

  response_templates = {
    "application/json" = "{\"message\":$context.error.messageString}"
  }

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'${local.cors_origin}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
  }
}

resource "aws_api_gateway_gateway_response" "default_5xx" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  response_type = "DEFAULT_5XX"

  response_templates = {
    "application/json" = "{\"message\":$context.error.messageString}"
  }

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'${local.cors_origin}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
  }
}

# ─── CloudWatch Log Group for Access Logs ────────────────────────────────────

resource "aws_cloudwatch_log_group" "access_logs" {
  name              = "/aws/apigateway/${local.api_name}/access-logs"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "/aws/apigateway/${local.api_name}/access-logs"
  })
}

# ─── /health Resource ────────────────────────────────────────────────────────

resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = "health"
}

resource "aws_api_gateway_method" "health_get" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.health.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "health_get" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "health_get_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "health_get_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.health.id
  http_method = aws_api_gateway_method.health_get.http_method
  status_code = aws_api_gateway_method_response.health_get_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = "'${local.cors_origin}'"
  }

  response_templates = {
    "application/json" = jsonencode({ status = "healthy" })
  }
}

# ─── /chat Resource ──────────────────────────────────────────────────────────

resource "aws_api_gateway_resource" "chat" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = "chat"
}

# ─── /chat/query Resource ────────────────────────────────────────────────────

resource "aws_api_gateway_resource" "chat_query" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_resource.chat.id
  path_part   = "query"
}

resource "aws_api_gateway_method" "chat_query_post" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.chat_query.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "chat_query_post" {
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_resource.chat_query.id
  http_method             = aws_api_gateway_method.chat_query_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.chat_handler_invoke_arn
}

resource "aws_api_gateway_method_response" "chat_query_post_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.chat_query.id
  http_method = aws_api_gateway_method.chat_query_post.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

# CORS OPTIONS for /chat/query
resource "aws_api_gateway_method" "chat_query_options" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.chat_query.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "chat_query_options" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.chat_query.id
  http_method = aws_api_gateway_method.chat_query_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "chat_query_options_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.chat_query.id
  http_method = aws_api_gateway_method.chat_query_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "chat_query_options_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.chat_query.id
  http_method = aws_api_gateway_method.chat_query_options.http_method
  status_code = aws_api_gateway_method_response.chat_query_options_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_origin}'"
  }
}

# ─── /chat/history/{sessionId} Resource ─────────────────────────────────────

resource "aws_api_gateway_resource" "chat_history" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_resource.chat.id
  path_part   = "history"
}

resource "aws_api_gateway_resource" "chat_history_session" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_resource.chat_history.id
  path_part   = "{sessionId}"
}

resource "aws_api_gateway_method" "chat_history_get" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.chat_history_session.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.sessionId" = true
  }
}

resource "aws_api_gateway_integration" "chat_history_get" {
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_resource.chat_history_session.id
  http_method             = aws_api_gateway_method.chat_history_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.chat_handler_invoke_arn
}

resource "aws_api_gateway_method_response" "chat_history_get_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.chat_history_session.id
  http_method = aws_api_gateway_method.chat_history_get.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

# CORS OPTIONS for /chat/history/{sessionId}
resource "aws_api_gateway_method" "chat_history_options" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.chat_history_session.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "chat_history_options" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.chat_history_session.id
  http_method = aws_api_gateway_method.chat_history_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "chat_history_options_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.chat_history_session.id
  http_method = aws_api_gateway_method.chat_history_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "chat_history_options_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.chat_history_session.id
  http_method = aws_api_gateway_method.chat_history_options.http_method
  status_code = aws_api_gateway_method_response.chat_history_options_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_origin}'"
  }
}

# ─── /documents Resource ──────────────────────────────────────────────────────

resource "aws_api_gateway_resource" "documents" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = "documents"
}

# POST /documents (Upload)
resource "aws_api_gateway_method" "documents_post" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.documents.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "documents_post" {
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_resource.documents.id
  http_method             = aws_api_gateway_method.documents_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.document_manager_invoke_arn
}

resource "aws_api_gateway_method_response" "documents_post_202" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.documents.id
  http_method = aws_api_gateway_method.documents_post.http_method
  status_code = "202"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

# GET /documents (List)
resource "aws_api_gateway_method" "documents_get" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.documents.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "documents_get" {
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_resource.documents.id
  http_method             = aws_api_gateway_method.documents_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.document_manager_invoke_arn
}

resource "aws_api_gateway_method_response" "documents_get_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.documents.id
  http_method = aws_api_gateway_method.documents_get.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

# CORS OPTIONS for /documents
resource "aws_api_gateway_method" "documents_options" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.documents.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "documents_options" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.documents.id
  http_method = aws_api_gateway_method.documents_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "documents_options_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.documents.id
  http_method = aws_api_gateway_method.documents_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "documents_options_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.documents.id
  http_method = aws_api_gateway_method.documents_options.http_method
  status_code = aws_api_gateway_method_response.documents_options_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_origin}'"
  }
}

# ─── /documents/{documentId} Resource ─────────────────────────────────────────

resource "aws_api_gateway_resource" "documents_id" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_resource.documents.id
  path_part   = "{documentId}"
}

# GET /documents/{documentId} (Get Details)
resource "aws_api_gateway_method" "documents_id_get" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.documents_id.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.documentId" = true
  }
}

resource "aws_api_gateway_integration" "documents_id_get" {
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_resource.documents_id.id
  http_method             = aws_api_gateway_method.documents_id_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.document_manager_invoke_arn
}

resource "aws_api_gateway_method_response" "documents_id_get_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.documents_id.id
  http_method = aws_api_gateway_method.documents_id_get.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

# DELETE /documents/{documentId}
resource "aws_api_gateway_method" "documents_id_delete" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.documents_id.id
  http_method   = "DELETE"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.documentId" = true
  }
}

resource "aws_api_gateway_integration" "documents_id_delete" {
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_resource.documents_id.id
  http_method             = aws_api_gateway_method.documents_id_delete.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.document_manager_invoke_arn
}

resource "aws_api_gateway_method_response" "documents_id_delete_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.documents_id.id
  http_method = aws_api_gateway_method.documents_id_delete.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

# CORS OPTIONS for /documents/{documentId}
resource "aws_api_gateway_method" "documents_id_options" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  resource_id   = aws_api_gateway_resource.documents_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "documents_id_options" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.documents_id.id
  http_method = aws_api_gateway_method.documents_id_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_api_gateway_method_response" "documents_id_options_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.documents_id.id
  http_method = aws_api_gateway_method.documents_id_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "documents_id_options_200" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  resource_id = aws_api_gateway_resource.documents_id.id
  http_method = aws_api_gateway_method.documents_id_options.http_method
  status_code = aws_api_gateway_method_response.documents_id_options_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${local.cors_origin}'"
  }
}

# ─── Deployment & Stage ───────────────────────────────────────────────────────

resource "aws_api_gateway_deployment" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.health.id,
      aws_api_gateway_method.health_get.id,
      aws_api_gateway_integration.health_get.id,
      aws_api_gateway_resource.chat_query.id,
      aws_api_gateway_method.chat_query_post.id,
      aws_api_gateway_integration.chat_query_post.id,
      aws_api_gateway_resource.chat_history_session.id,
      aws_api_gateway_method.chat_history_get.id,
      aws_api_gateway_integration.chat_history_get.id,
      aws_api_gateway_resource.documents.id,
      aws_api_gateway_method.documents_post.id,
      aws_api_gateway_integration.documents_post.id,
      aws_api_gateway_method.documents_get.id,
      aws_api_gateway_integration.documents_get.id,
      aws_api_gateway_resource.documents_id.id,
      aws_api_gateway_method.documents_id_get.id,
      aws_api_gateway_integration.documents_id_get.id,
      aws_api_gateway_method.documents_id_delete.id,
      aws_api_gateway_integration.documents_id_delete.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.health_get,
    aws_api_gateway_integration.chat_query_post,
    aws_api_gateway_integration.chat_query_options,
    aws_api_gateway_integration.chat_history_get,
    aws_api_gateway_integration.chat_history_options,
    aws_api_gateway_integration.documents_post,
    aws_api_gateway_integration.documents_get,
    aws_api_gateway_integration.documents_options,
    aws_api_gateway_integration.documents_id_get,
    aws_api_gateway_integration.documents_id_delete,
    aws_api_gateway_integration.documents_id_options,
  ]
}

resource "aws_api_gateway_stage" "this" {
  deployment_id = aws_api_gateway_deployment.this.id
  rest_api_id   = aws_api_gateway_rest_api.this.id
  stage_name    = local.stage_name

  # Commenting out access logging to avoid CloudWatch Logs role requirement
  # access_log_settings {
  #   destination_arn = aws_cloudwatch_log_group.access_logs.arn
  #   format = jsonencode({
  #     requestId      = "$context.requestId"
  #     ip             = "$context.identity.sourceIp"
  #     caller         = "$context.identity.caller"
  #     user           = "$context.identity.user"
  #     requestTime    = "$context.requestTime"
  #     httpMethod     = "$context.httpMethod"
  #     resourcePath   = "$context.resourcePath"
  #     status         = "$context.status"
  #     protocol       = "$context.protocol"
  #     responseLength = "$context.responseLength"
  #     errorMessage   = "$context.error.message"
  #   })
  # }

  tags = merge(var.tags, {
    Name = "${local.api_name}-${local.stage_name}"
  })
}

resource "aws_api_gateway_method_settings" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  stage_name  = aws_api_gateway_stage.this.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled    = true
    logging_level      = "OFF" # Disabled to avoid CloudWatch Logs role requirement
    data_trace_enabled = false

    throttling_burst_limit = var.throttling_burst_limit
    throttling_rate_limit  = var.throttling_rate_limit
  }
}
