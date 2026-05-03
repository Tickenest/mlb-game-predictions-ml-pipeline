Write-Host "Building and pushing mlb-predictions-prediction container image..."

# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 --profile mlb-predictions-dev | docker login --username AWS --password-stdin 387873491220.dkr.ecr.us-east-1.amazonaws.com

# Build image
Write-Host "Building Docker image..."
docker build --platform linux/amd64 --provenance=false `
    -t mlb-predictions-prediction `
    backend/prediction/

# Tag image
docker tag mlb-predictions-prediction:latest `
    387873491220.dkr.ecr.us-east-1.amazonaws.com/mlb-predictions-prediction:latest

# Push to ECR
Write-Host "Pushing to ECR..."
docker push 387873491220.dkr.ecr.us-east-1.amazonaws.com/mlb-predictions-prediction:latest

Write-Host "Prediction Lambda container image deployed successfully."