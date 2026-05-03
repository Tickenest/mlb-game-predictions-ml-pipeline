Write-Host "Deploying mlb-predictions-query Lambda..."

if (Test-Path package_query) { Remove-Item -Recurse -Force package_query }
if (Test-Path deployment_query.zip) { Remove-Item deployment_query.zip }

New-Item -ItemType Directory -Path package_query | Out-Null

Write-Host "Installing dependencies..."
docker run --name query_build python:3.12 `
    pip install boto3 pandas -t /package
docker cp query_build:/package/. ./package_query/
docker rm query_build

Write-Host "Stripping unnecessary files..."
Get-ChildItem -Path package_query -Recurse -Include "*.egg-info" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_query -Recurse -Include "*.pyc" | Remove-Item -Force
Get-ChildItem -Path package_query -Recurse -Include "__pycache__" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_query -Recurse -Include "*.pyi" | Remove-Item -Force
Get-ChildItem -Path package_query -Recurse -Include "*.md" | Remove-Item -Force
Get-ChildItem -Path package_query -Recurse -Include "*.rst" | Remove-Item -Force

if (Test-Path package_query/boto3) { Remove-Item -Recurse -Force package_query/boto3 }
if (Test-Path package_query/botocore) { Remove-Item -Recurse -Force package_query/botocore }
if (Test-Path package_query/s3transfer) { Remove-Item -Recurse -Force package_query/s3transfer }
if (Test-Path package_query/urllib3) { Remove-Item -Recurse -Force package_query/urllib3 }

Write-Host "Copying function code..."
Copy-Item backend/query/lambda_function.py package_query/

Write-Host "Creating deployment zip..."
Compress-Archive -Path package_query/* -DestinationPath deployment_query.zip

$zipSize = (Get-Item deployment_query.zip).Length / 1MB
Write-Host "Zip size: $([math]::Round($zipSize, 1)) MB"

Write-Host "Uploading to S3..."
aws s3 cp deployment_query.zip `
    s3://mlb-predictions-data-46bc5aeb/deployments/deployment_query.zip `
    --profile mlb-predictions-dev

Write-Host "Deploying to Lambda..."
aws lambda update-function-code `
    --function-name mlb-predictions-query `
    --s3-bucket mlb-predictions-data-46bc5aeb `
    --s3-key deployments/deployment_query.zip `
    --profile mlb-predictions-dev

Write-Host "Query Lambda deployed successfully."