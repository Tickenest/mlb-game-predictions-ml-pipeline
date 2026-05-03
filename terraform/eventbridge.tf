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

resource "aws_cloudwatch_event_rule" "daily_prediction" {
  name                = "${var.project_name}-daily-prediction"
  description         = "Triggers MLB prediction generation daily at 1 PM ET"
  schedule_expression = "cron(30 16 * * ? *)"
}

resource "aws_cloudwatch_event_target" "daily_prediction" {
  rule      = aws_cloudwatch_event_rule.daily_prediction.name
  target_id = "prediction-lambda"
  arn       = aws_lambda_function.prediction.arn
}

resource "aws_lambda_permission" "eventbridge_prediction" {
  statement_id  = "AllowEventBridgePrediction"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.prediction.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_prediction.arn
}