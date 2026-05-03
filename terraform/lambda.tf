# ── Ingestion Lambda ───────────────────────────────────────────────────
resource "aws_lambda_function" "ingestion" {
  function_name = "${var.project_name}-ingestion"
  role          = aws_iam_role.lambda_ingestion.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  filename         = "${path.module}/placeholder.zip"
  source_code_hash = filebase64sha256("${path.module}/placeholder.zip")

  environment {
    variables = {
      DATA_BUCKET = aws_s3_bucket.data.id
    }
  }
}

resource "aws_cloudwatch_log_group" "ingestion" {
  name              = "/aws/lambda/${aws_lambda_function.ingestion.function_name}"
  retention_in_days = 30
}

# ── Pipeline Trigger Lambda ────────────────────────────────────────────
resource "aws_lambda_function" "pipeline_trigger" {
  function_name = "${var.project_name}-pipeline-trigger"
  role          = aws_iam_role.lambda_pipeline_trigger.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  timeout       = 60
  memory_size   = 256

  filename         = "${path.module}/placeholder.zip"
  source_code_hash = filebase64sha256("${path.module}/placeholder.zip")

  environment {
    variables = {
      PIPELINE_NAME = "${var.project_name}-training-pipeline"
    }
  }
}

resource "aws_cloudwatch_log_group" "pipeline_trigger" {
  name              = "/aws/lambda/${aws_lambda_function.pipeline_trigger.function_name}"
  retention_in_days = 30
}

# Allow S3 to invoke pipeline trigger Lambda
resource "aws_lambda_permission" "s3_pipeline_trigger" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pipeline_trigger.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.data.arn
}

# ── Prediction Lambda ──────────────────────────────────────────────────
resource "aws_lambda_function" "prediction" {
  function_name = "${var.project_name}-prediction"
  role          = aws_iam_role.lambda_prediction.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  timeout       = var.lambda_timeout
  memory_size   = 1024

  filename         = "${path.module}/placeholder.zip"
  source_code_hash = filebase64sha256("${path.module}/placeholder.zip")

  environment {
    variables = {
      DATA_BUCKET            = aws_s3_bucket.data.id
      SAGEMAKER_ENDPOINT     = "${var.project_name}-serverless-endpoint"
    }
  }
}

resource "aws_cloudwatch_log_group" "prediction" {
  name              = "/aws/lambda/${aws_lambda_function.prediction.function_name}"
  retention_in_days = 30
}

# ── Query Lambda ───────────────────────────────────────────────────────
resource "aws_lambda_function" "query" {
  function_name = "${var.project_name}-query"
  role          = aws_iam_role.lambda_query.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  timeout       = 30
  memory_size   = 256

  filename         = "${path.module}/placeholder.zip"
  source_code_hash = filebase64sha256("${path.module}/placeholder.zip")

  environment {
    variables = {
      DATA_BUCKET = aws_s3_bucket.data.id
    }
  }
}

resource "aws_cloudwatch_log_group" "query" {
  name              = "/aws/lambda/${aws_lambda_function.query.function_name}"
  retention_in_days = 30
}