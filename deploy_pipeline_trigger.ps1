Write-Host "Deploying mlb-predictions-pipeline-trigger Lambda..."

if (Test-Path package_pipeline_trigger) { Remove-Item -Recurse -Force package_pipeline_trigger }
if (Test-Path deployment_pipeline_trigger.zip) { Remove-Item deployment_pipeline_trigger.zip }

New-Item -ItemType Directory -Path package_pipeline_trigger | Out-Null

Write-Host "Installing dependencies..."
docker run --name pipeline_trigger_build python:3.12 `
    pip install boto3 -t /package
docker cp pipeline_trigger_build:/package/. ./package_pipeline_trigger/
docker rm pipeline_trigger_build

Write-Host "Stripping unnecessary files..."
Get-ChildItem -Path package_pipeline_trigger -Recurse -Include "*.egg-info" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_pipeline_trigger -Recurse -Include "*.pyc" | Remove-Item -Force
Get-ChildItem -Path package_pipeline_trigger -Recurse -Include "__pycache__" -Directory | Remove-Item -Recurse -Force

if (Test-Path package_pipeline_trigger/boto3) { Remove-Item -Recurse -Force package_pipeline_trigger/boto3 }
if (Test-Path package_pipeline_trigger/botocore) { Remove-Item -Recurse -Force package_pipeline_trigger/botocore }
if (Test-Path package_pipeline_trigger/s3transfer) { Remove-Item -Recurse -Force package_pipeline_trigger/s3transfer }
if (Test-Path package_pipeline_trigger/urllib3) { Remove-Item -Recurse -Force package_pipeline_trigger/urllib3 }

Write-Host "Copying function code..."
Copy-Item backend/pipeline_trigger/lambda_function.py package_pipeline_trigger/

Write-Host "Creating deployment zip..."
Compress-Archive -Path package_pipeline_trigger/* -DestinationPath deployment_pipeline_trigger.zip

$zipSize = (Get-Item deployment_pipeline_trigger.zip).Length / 1MB
Write-Host "Zip size: $([math]::Round($zipSize, 1)) MB"

Write-Host "Uploading to S3..."
aws s3 cp deployment_pipeline_trigger.zip `
    s3://mlb-predictions-data-46bc5aeb/deployments/deployment_pipeline_trigger.zip `
    --profile mlb-predictions-dev

Write-Host "Deploying to Lambda..."
aws lambda update-function-code `
    --function-name mlb-predictions-pipeline-trigger `
    --s3-bucket mlb-predictions-data-46bc5aeb `
    --s3-key deployments/deployment_pipeline_trigger.zip `
    --profile mlb-predictions-dev

Write-Host "Pipeline trigger Lambda deployed successfully."