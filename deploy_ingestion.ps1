Write-Host "Deploying mlb-predictions-ingestion Lambda..."

if (Test-Path package_ingestion) { Remove-Item -Recurse -Force package_ingestion }
if (Test-Path deployment_ingestion.zip) { Remove-Item deployment_ingestion.zip }

New-Item -ItemType Directory -Path package_ingestion | Out-Null

Write-Host "Installing dependencies..."
docker run --name ingestion_build python:3.12 `
    pip install requests pandas boto3 -t /package
docker cp ingestion_build:/package/. ./package_ingestion/
docker rm ingestion_build

Write-Host "Stripping unnecessary files..."
Get-ChildItem -Path package_ingestion -Recurse -Include "*.egg-info" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_ingestion -Recurse -Include "tests" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_ingestion -Recurse -Include "*.pyc" | Remove-Item -Force
Get-ChildItem -Path package_ingestion -Recurse -Include "__pycache__" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_ingestion -Recurse -Include "*.pyi" | Remove-Item -Force
Get-ChildItem -Path package_ingestion -Recurse -Include "*.md" | Remove-Item -Force
Get-ChildItem -Path package_ingestion -Recurse -Include "*.rst" | Remove-Item -Force

if (Test-Path package_ingestion/boto3) { Remove-Item -Recurse -Force package_ingestion/boto3 }
if (Test-Path package_ingestion/botocore) { Remove-Item -Recurse -Force package_ingestion/botocore }
if (Test-Path package_ingestion/s3transfer) { Remove-Item -Recurse -Force package_ingestion/s3transfer }
if (Test-Path package_ingestion/urllib3) { Remove-Item -Recurse -Force package_ingestion/urllib3 }

Write-Host "Copying function code..."
Copy-Item backend/ingestion/lambda_function.py package_ingestion/

Write-Host "Creating deployment zip..."
Compress-Archive -Path package_ingestion/* -DestinationPath deployment_ingestion.zip

$zipSize = (Get-Item deployment_ingestion.zip).Length / 1MB
Write-Host "Zip size: $([math]::Round($zipSize, 1)) MB"

Write-Host "Uploading to S3..."
aws s3 cp deployment_ingestion.zip `
    s3://mlb-predictions-data-46bc5aeb/deployments/deployment_ingestion.zip `
    --profile mlb-predictions-dev

Write-Host "Deploying to Lambda..."
aws lambda update-function-code `
    --function-name mlb-predictions-ingestion `
    --s3-bucket mlb-predictions-data-46bc5aeb `
    --s3-key deployments/deployment_ingestion.zip `
    --profile mlb-predictions-dev

Write-Host "Ingestion Lambda deployed successfully."