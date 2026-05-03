Write-Host "Deploying mlb-predictions-prediction Lambda..."

if (Test-Path package_prediction) { Remove-Item -Recurse -Force package_prediction }
if (Test-Path deployment_prediction.zip) { Remove-Item deployment_prediction.zip }

New-Item -ItemType Directory -Path package_prediction | Out-Null

Write-Host "Installing dependencies..."
docker run --name prediction_build python:3.12 `
    pip install requests pandas numpy scikit-learn xgboost boto3 -t /package
docker cp prediction_build:/package/. ./package_prediction/
docker rm prediction_build

Write-Host "Stripping unnecessary files..."
Get-ChildItem -Path package_prediction -Recurse -Include "*.egg-info" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_prediction -Recurse -Include "tests" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_prediction -Recurse -Include "*.pyc" | Remove-Item -Force
Get-ChildItem -Path package_prediction -Recurse -Include "__pycache__" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_prediction -Recurse -Include "*.pyi" | Remove-Item -Force
Get-ChildItem -Path package_prediction -Recurse -Include "*.md" | Remove-Item -Force
Get-ChildItem -Path package_prediction -Recurse -Include "*.rst" | Remove-Item -Force

if (Test-Path package_prediction/boto3) { Remove-Item -Recurse -Force package_prediction/boto3 }
if (Test-Path package_prediction/botocore) { Remove-Item -Recurse -Force package_prediction/botocore }
if (Test-Path package_prediction/s3transfer) { Remove-Item -Recurse -Force package_prediction/s3transfer }
if (Test-Path package_prediction/urllib3) { Remove-Item -Recurse -Force package_prediction/urllib3 }

# Additional aggressive stripping for large ML packages
Get-ChildItem -Path package_prediction -Recurse -Include "*.h" | Remove-Item -Force
Get-ChildItem -Path package_prediction -Recurse -Include "*.c" | Remove-Item -Force
Get-ChildItem -Path package_prediction -Recurse -Include "*.cpp" | Remove-Item -Force
Get-ChildItem -Path package_prediction -Recurse -Include "*.pyx" | Remove-Item -Force
Get-ChildItem -Path package_prediction -Recurse -Include "examples" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_prediction -Recurse -Include "docs" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_prediction -Recurse -Include "doc" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path package_prediction -Recurse -Include "*.txt" | Remove-Item -Force
Get-ChildItem -Path package_prediction -Recurse -Include "dist-info" -Directory | Remove-Item -Recurse -Force

# Remove numpy test data and f2py which are large and unused
if (Test-Path package_prediction/numpy/core/tests) { Remove-Item -Recurse -Force package_prediction/numpy/core/tests }
if (Test-Path package_prediction/numpy/f2py) { Remove-Item -Recurse -Force package_prediction/numpy/f2py }
if (Test-Path package_prediction/numpy/distutils) { Remove-Item -Recurse -Force package_prediction/numpy/distutils }
if (Test-Path package_prediction/scipy) { Remove-Item -Recurse -Force package_prediction/scipy }

Write-Host "Copying function code..."
Copy-Item backend/prediction/lambda_function.py package_prediction/

$unzippedSize = (Get-ChildItem -Path package_prediction -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "Unzipped size: $([math]::Round($unzippedSize, 1)) MB"

Write-Host "Creating deployment zip..."
Compress-Archive -Path package_prediction/* -DestinationPath deployment_prediction.zip

$zipSize = (Get-Item deployment_prediction.zip).Length / 1MB
Write-Host "Zip size: $([math]::Round($zipSize, 1)) MB"

Write-Host "Uploading to S3..."
aws s3 cp deployment_prediction.zip `
    s3://mlb-predictions-data-46bc5aeb/deployments/deployment_prediction.zip `
    --profile mlb-predictions-dev

Write-Host "Deploying to Lambda..."
aws lambda update-function-code `
    --function-name mlb-predictions-prediction `
    --s3-bucket mlb-predictions-data-46bc5aeb `
    --s3-key deployments/deployment_prediction.zip `
    --profile mlb-predictions-dev

Write-Host "Prediction Lambda deployed successfully."