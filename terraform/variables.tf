variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "mlb-predictions"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "sagemaker_execution_role_arn" {
  description = "ARN of the SageMaker execution role"
  type        = string
}

variable "daily_schedule" {
  description = "EventBridge cron schedule for daily pipeline trigger"
  type        = string
  default     = "cron(0 12 * * ? *)"  # 8 AM ET (noon UTC)
}

variable "model_accuracy_threshold" {
  description = "Minimum accuracy improvement to promote a new model"
  type        = number
  default     = 0.001
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 300
}

variable "lambda_memory" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 512
}