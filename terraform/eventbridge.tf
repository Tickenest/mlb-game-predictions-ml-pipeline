# Daily trigger for ingestion Lambda
resource "aws_cloudwatch_event_rule" "daily_ingestion" {
  name                = "${var.project_name}-daily-ingestion"
  description         = "Triggers MLB data ingestion daily at 8 AM ET"
  schedule_expression = var.daily_schedule
}

resource "aws_cloudwatch_event_target" "daily_ingestion" {
  rule      = aws_cloudwatch_event_rule.daily_ingestion.name
  target_id = "ingestion-lambda"
  arn       = aws_lambda_function.ingestion.arn
}

resource "aws_lambda_permission" "eventbridge_ingestion" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_ingestion.arn
}