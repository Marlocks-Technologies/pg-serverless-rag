resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "/aws/lambda/${var.function_name}"
  })
}

resource "aws_lambda_function" "this" {
  function_name = var.function_name
  handler       = var.handler
  runtime       = var.runtime
  filename      = var.filename
  role          = var.role_arn

  source_code_hash = var.source_code_hash
  memory_size      = var.memory_size
  timeout          = var.timeout
  layers           = var.layers

  reserved_concurrent_executions = var.reserved_concurrent_executions

  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [1] : []
    content {
      variables = var.environment_variables
    }
  }

  dynamic "vpc_config" {
    for_each = var.vpc_config != null ? [var.vpc_config] : []
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }

  depends_on = [aws_cloudwatch_log_group.this]

  tags = merge(var.tags, {
    Name = var.function_name
  })
}

# Allow S3 to invoke this Lambda
resource "aws_lambda_permission" "s3_invocation" {
  count = var.allow_s3_invocation ? 1 : 0

  statement_id  = "AllowS3Invocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = var.s3_source_bucket_arn
}

# Allow API Gateway to invoke this Lambda
resource "aws_lambda_permission" "apigateway_invocation" {
  count = var.allow_apigateway_invocation ? 1 : 0

  statement_id  = "AllowAPIGatewayInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = var.apigateway_source_arn
}
