# update_endpoint.ps1
# Finds the most recently approved model in the registry and updates the endpoint

$PROFILE = "mlb-predictions-dev"
$REGION = "us-east-1"
$MODEL_GROUP = "mlb-predictions-models"
$ENDPOINT_NAME = "mlb-predictions-serverless-endpoint"
$ROLE_ARN = "arn:aws:iam::387873491220:role/mlb-predictions-sagemaker-role"
$XGBOOST_IMAGE = "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-xgboost:1.7-1"

Write-Host "Finding latest approved model..."

# Get all approved models sorted by creation time
$packages = aws sagemaker list-model-packages `
    --model-package-group-name $MODEL_GROUP `
    --model-approval-status Approved `
    --sort-by CreationTime `
    --sort-order Descending `
    --profile $PROFILE `
    --region $REGION | ConvertFrom-Json

if ($packages.ModelPackageSummaryList.Count -eq 0) {
    Write-Host "ERROR: No approved models found in registry."
    Write-Host "Run the pipeline and approve a model first."
    exit 1
}

$latest = $packages.ModelPackageSummaryList[0]
$modelPackageArn = $latest.ModelPackageArn
$version = $latest.ModelPackageVersion
Write-Host "Latest approved model: version $version"
Write-Host "ARN: $modelPackageArn"

# Get the model artifact URI from the package
$packageDetail = aws sagemaker describe-model-package `
    --model-package-name $modelPackageArn `
    --profile $PROFILE `
    --region $REGION | ConvertFrom-Json

$modelDataUrl = $packageDetail.InferenceSpecification.Containers[0].ModelDataUrl
Write-Host "Model artifact: $modelDataUrl"

# Create a new SageMaker model with a timestamp-based name
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$modelName = "mlb-predictions-model-$timestamp"

Write-Host "Creating SageMaker model: $modelName..."
aws sagemaker create-model `
    --model-name $modelName `
    --execution-role-arn $ROLE_ARN `
    --primary-container "Image=$XGBOOST_IMAGE,ModelDataUrl=$modelDataUrl" `
    --profile $PROFILE `
    --region $REGION | Out-Null

# Create a new endpoint config
$configName = "mlb-predictions-serverless-config-$timestamp"
Write-Host "Creating endpoint config: $configName..."
aws sagemaker create-endpoint-config `
    --endpoint-config-name $configName `
    --production-variants "VariantName=primary,ModelName=$modelName,ServerlessConfig={MemorySizeInMB=2048,MaxConcurrency=5}" `
    --profile $PROFILE `
    --region $REGION | Out-Null

# Update the endpoint to use the new config
Write-Host "Updating endpoint..."
aws sagemaker update-endpoint `
    --endpoint-name $ENDPOINT_NAME `
    --endpoint-config-name $configName `
    --profile $PROFILE `
    --region $REGION | Out-Null

Write-Host ""
Write-Host "Endpoint update initiated. Waiting for it to become InService..."
Write-Host "(This takes 2-3 minutes)"

# Poll until endpoint is InService
$maxWait = 20
$waited = 0
while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 15
    $waited++
    $status = aws sagemaker describe-endpoint `
        --endpoint-name $ENDPOINT_NAME `
        --profile $PROFILE `
        --region $REGION `
        --query EndpointStatus `
        --output text
    Write-Host "  Status: $status"
    if ($status -eq "InService") {
        break
    }
    if ($status -eq "Failed") {
        Write-Host "ERROR: Endpoint update failed."
        exit 1
    }
}

if ($waited -ge $maxWait) {
    Write-Host "Timeout waiting for endpoint. Check AWS console for status."
    exit 1
}

Write-Host ""
Write-Host "Endpoint updated successfully to model version $version."

# Cleanup — delete old models and endpoint configs (keep only the current one)
Write-Host ""
Write-Host "Cleaning up old models and endpoint configs..."

# Delete old endpoint configs (all except the one we just created)
$configs = aws sagemaker list-endpoint-configs `
    --name-contains "mlb-predictions-serverless-config" `
    --profile $PROFILE `
    --region $REGION | ConvertFrom-Json

$deletedConfigs = 0
foreach ($config in $configs.EndpointConfigs) {
    if ($config.EndpointConfigName -ne $configName) {
        aws sagemaker delete-endpoint-config `
            --endpoint-config-name $config.EndpointConfigName `
            --profile $PROFILE `
            --region $REGION | Out-Null
        $deletedConfigs++
    }
}
Write-Host "  Deleted $deletedConfigs old endpoint configs."

# Delete old models (all mlb-predictions-model-* except the one we just created)
$models = aws sagemaker list-models `
    --name-contains "mlb-predictions-model-" `
    --profile $PROFILE `
    --region $REGION | ConvertFrom-Json

$deletedModels = 0
foreach ($model in $models.Models) {
    if ($model.ModelName -ne $modelName) {
        aws sagemaker delete-model `
            --model-name $model.ModelName `
            --profile $PROFILE `
            --region $REGION | Out-Null
        $deletedModels++
    }
}
Write-Host "  Deleted $deletedModels old models."

Write-Host ""
Write-Host "Done. Endpoint is serving model version $version."