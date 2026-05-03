output "data_bucket_name" {
  value = aws_s3_bucket.data.id
}

output "frontend_bucket_name" {
  value = aws_s3_bucket.frontend.id
}

output "sagemaker_bucket_name" {
  value = aws_s3_bucket.sagemaker.id
}

output "frontend_url" {
  value = "http://${aws_s3_bucket.frontend.id}.s3-website-${var.aws_region}.amazonaws.com"
}

output "sagemaker_role_arn" {
  value = aws_iam_role.sagemaker_execution.arn
}

output "api_gateway_url" {
  value = "${aws_api_gateway_stage.prod.invoke_url}"
}

output "api_key_id" {
  value = aws_api_gateway_api_key.main.id
}