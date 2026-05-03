# ── SageMaker Model Group (Model Registry) ─────────────────────────────
resource "aws_sagemaker_model_package_group" "main" {
  model_package_group_name        = "${var.project_name}-models"
  model_package_group_description = "MLB game outcome prediction models"
}

# ── SageMaker Pipeline ─────────────────────────────────────────────────
resource "aws_sagemaker_pipeline" "training" {
  pipeline_name         = "${var.project_name}-training-pipeline"
  pipeline_display_name = "${var.project_name}-training-pipeline"
  pipeline_description  = "MLOps pipeline for MLB game predictions"
  role_arn              = aws_iam_role.sagemaker_execution.arn

  pipeline_definition = jsonencode({
    Version = "2020-12-01"
    Parameters = [
      {
        Name         = "DataBucket"
        Type         = "String"
        DefaultValue = aws_s3_bucket.data.id
      },
      {
        Name         = "SageMakerBucket"
        Type         = "String"
        DefaultValue = aws_s3_bucket.sagemaker.id
      },
      {
        Name         = "ModelPackageGroup"
        Type         = "String"
        DefaultValue = aws_sagemaker_model_package_group.main.model_package_group_name
      },
      {
        Name         = "AccuracyThreshold"
        Type         = "Float"
        DefaultValue = var.model_accuracy_threshold
      },
    ]
    Steps = [
      # Step 1 — Feature Engineering
      {
        Name = "FeatureEngineering"
        Type = "Processing"
        Arguments = {
          ProcessingResources = {
            ClusterConfig = {
              InstanceCount  = 1
              InstanceType   = "ml.t3.medium"
              VolumeSizeInGB = 10
            }
          }
          AppSpecification = {
            ImageUri            = "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1"
            ContainerEntrypoint = ["python3", "/opt/ml/processing/input/code/engineer_v2.py"]
          }
          ProcessingInputs = [
            {
              InputName = "code"
              S3Input = {
                S3Uri         = "s3://${aws_s3_bucket.data.id}/code/engineer_v2.py"
                LocalPath     = "/opt/ml/processing/input/code"
                S3DataType    = "S3Prefix"
                S3InputMode   = "File"
              }
            },
            {
              InputName = "raw_data"
              S3Input = {
                S3Uri         = "s3://${aws_s3_bucket.data.id}/raw/"
                LocalPath     = "/opt/ml/processing/input/raw"
                S3DataType    = "S3Prefix"
                S3InputMode   = "File"
              }
            },
          ]
          ProcessingOutputConfig = {
            Outputs = [
              {
                OutputName = "features"
                S3Output = {
                  S3Uri         = "s3://${aws_s3_bucket.sagemaker.id}/features/"
                  LocalPath     = "/opt/ml/processing/output"
                  S3UploadMode  = "EndOfJob"
                }
              }
            ]
          }
        }
      },

      # Step 2 — Training
      {
        Name      = "Training"
        Type      = "Training"
        DependsOn = ["FeatureEngineering"]
        Arguments = {
          AlgorithmSpecification = {
            TrainingImage     = "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-xgboost:1.7-1"
            TrainingInputMode = "File"
          }
          ResourceConfig = {
            InstanceCount  = 1
            InstanceType   = "ml.m5.large"
            VolumeSizeInGB = 10
          }
          StoppingCondition = {
            MaxRuntimeInSeconds = 3600
          }
          OutputDataConfig = {
            S3OutputPath = "s3://${aws_s3_bucket.sagemaker.id}/models/"
          }
          InputDataConfig = [
            {
              ChannelName = "train"
              DataSource = {
                S3DataSource = {
                  S3Uri            = "s3://${aws_s3_bucket.sagemaker.id}/features/train/"
                  S3DataType       = "S3Prefix"
                  S3DataDistributionType = "FullyReplicated"
                }
              }
              ContentType = "text/csv"
            }
          ]
          HyperParameters = {
            num_round        = "300"
            max_depth        = "4"
            eta              = "0.05"
            subsample        = "0.8"
            colsample_bytree = "0.8"
            min_child_weight = "5"
            objective        = "binary:logistic"
            eval_metric      = "logloss"
          }
        }
      },

      # Step 3 — Evaluation
      {
        Name      = "Evaluation"
        Type      = "Processing"
        DependsOn = ["Training"]
        Arguments = {
          ProcessingResources = {
            ClusterConfig = {
              InstanceCount  = 1
              InstanceType   = "ml.t3.medium"
              VolumeSizeInGB = 10
            }
          }
          AppSpecification = {
            ImageUri            = "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1"
            ContainerEntrypoint = ["python3", "/opt/ml/processing/input/code/evaluate.py"]
          }
          ProcessingInputs = [
            {
              InputName = "code"
              S3Input = {
                S3Uri         = "s3://${aws_s3_bucket.data.id}/code/evaluate.py"
                LocalPath     = "/opt/ml/processing/input/code"
                S3DataType    = "S3Prefix"
                S3InputMode   = "File"
              }
            },
            {
              InputName = "model"
              S3Input = {
                S3Uri         = "s3://${aws_s3_bucket.sagemaker.id}/models/"
                LocalPath     = "/opt/ml/processing/input/model"
                S3DataType    = "S3Prefix"
                S3InputMode   = "File"
              }
            },
            {
              InputName = "test_data"
              S3Input = {
                S3Uri         = "s3://${aws_s3_bucket.sagemaker.id}/features/test/"
                LocalPath     = "/opt/ml/processing/input/test"
                S3DataType    = "S3Prefix"
                S3InputMode   = "File"
              }
            },
          ]
          ProcessingOutputConfig = {
            Outputs = [
              {
                OutputName = "evaluation"
                S3Output = {
                  S3Uri        = "s3://${aws_s3_bucket.sagemaker.id}/evaluation/"
                  LocalPath    = "/opt/ml/processing/output"
                  S3UploadMode = "EndOfJob"
                }
              }
            ]
          }
        }
      },

      # Step 4 — Model Registration (conditional)
      {
        Name      = "RegisterModel"
        Type      = "RegisterModel"
        DependsOn = ["Evaluation"]
        Arguments = {
          ModelPackageGroupName = {
            "Get" = "Parameters.ModelPackageGroup"
          }
          ModelApprovalStatus = "PendingManualApproval"
          InferenceSpecification = {
            Containers = [
              {
                Image = "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-xgboost:1.7-1"
                ModelDataUrl = {
                  "Get" = "Steps.Training.ModelArtifacts.S3ModelArtifacts"
                }
              }
            ]
            SupportedContentTypes     = ["text/csv"]
            SupportedResponseMIMETypes = ["text/csv"]
          }
        }
      },
    ]
  })
}

# ── SageMaker Serverless Inference Endpoint ────────────────────────────
# resource "aws_sagemaker_endpoint_configuration" "serverless" {
#   name = "${var.project_name}-serverless-config"
# 
#   production_variants {
#     variant_name = "primary"
# 
#     serverless_config {
#       max_concurrency   = 5
#       memory_size_in_mb = 2048
#     }
#   }
# }