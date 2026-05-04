# MLB Game Predictions ML Pipeline

![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)
![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-FF9900?logo=awslambda&logoColor=white)
![SageMaker](https://img.shields.io/badge/AWS-SageMaker-FF9900?logo=amazonaws&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-ML-orange)
![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?logo=terraform&logoColor=white)

A full MLOps pipeline that predicts MLB game outcomes daily using XGBoost, AWS SageMaker, and a React frontend. The pipeline automatically ingests new game results, retrains the model, evaluates performance against a quality gate, registers improved models, and serves predictions via a SageMaker Serverless Inference endpoint — all without manual intervention.

---

## What It Does

Every day the pipeline:

1. **Ingests** yesterday's completed game results from the MLB Stats API
2. **Retrains** an XGBoost classifier on the updated dataset via SageMaker Pipelines
3. **Evaluates** the new model against the current production model
4. **Registers** the new model in SageMaker Model Registry if it improves accuracy
5. **Generates** win probability predictions for today's games at 12:30 PM ET
6. **Displays** predictions and recent results on a React dashboard

---

## Model Performance

The model predicts MLB game outcomes (home team win probability) using pre-game features:

| Metric | Value |
|--------|-------|
| Test Accuracy | 57.7% |
| AUC-ROC | 0.601 |
| Baseline (always predict home win) | 54.3% |
| Test Period | 2025-2026 seasons |
| Training Period | 2021-2024 seasons |

The most predictive features are starting pitcher ERA and WHIP — more predictive than team win rate or run differential — confirming the well-established baseball analytics finding that pitching drives game outcomes more than any other pre-game factor.

---

## Architecture

```
EventBridge (8 AM ET daily)
        |
Ingestion Lambda
  - Fetches yesterday's results from MLB Stats API
  - Appends to raw game results in S3
        |
S3 event notification
        |
Pipeline Trigger Lambda
        |
SageMaker Pipeline
  ├── Step 1: Feature Engineering (Processing Job — ml.t3.medium)
  │     - Rolling team stats (last 15 games)
  │     - Pitcher ERA, WHIP, SO9 joined from seasonal stats
  │     - Outputs train/test CSV to S3
  │
  ├── Step 2: Training (Training Job — ml.m5.large)
  │     - SageMaker built-in XGBoost algorithm
  │     - Trains on 2021-2024 game data
  │
  ├── Step 3: Evaluation (Processing Job — ml.t3.medium)
  │     - Evaluates on 2025-2026 holdout set
  │     - Compares against current production model
  │     - Quality gate: must improve accuracy by > 0.1%
  │
  └── Step 4: RegisterModel
        - Registers approved model in SageMaker Model Registry
        |
SageMaker Serverless Inference Endpoint
        |
EventBridge (12:30 PM ET daily)
        |
Prediction Lambda
  - Fetches today's probable starters from MLB Stats API
  - Builds feature vectors for each game
  - Calls SageMaker endpoint for win probabilities
  - Writes predictions JSON to S3
        |
API Gateway (REST, API key, throttled)
        |
Query Lambda
  - Serves predictions from S3
  - Enriches with actual outcomes from MLB Stats API
        |
React Frontend (S3 static website)
```

---

## Features Engineered

**Team features (rolling 15-game window):**
- Win rate
- Runs scored per game
- Runs allowed per game
- Run differential
- Home win rate (for home team)
- Away win rate (for away team)

**Pitcher features (seasonal stats from Baseball Reference):**
- Starting pitcher ERA
- Starting pitcher WHIP
- Starting pitcher strikeouts per 9 innings (SO9)

**Context features:**
- Month of season
- Day vs night game
- Home/away team encodings

---

## What Makes This Interesting

### Full MLOps Loop
Most ML projects stop at model training. This project implements the complete operational loop: daily data ingestion → automated retraining → quality-gated model registration → serverless inference → daily predictions. The model improves continuously as new season data accumulates.

### SageMaker Pipelines
The retraining pipeline is defined as a directed acyclic graph (DAG) of four steps using SageMaker's native pipeline orchestration. Each step runs on managed compute that spins up, executes, and shuts down — no always-on infrastructure. Step caching prevents unnecessary re-runs when inputs have not changed.

### Model Registry with Quality Gate
Every trained model is evaluated against the current production model before registration. If the new model does not improve accuracy by at least 0.1%, it is discarded. This prevents model degradation from noisy training runs and maintains a versioned history of every model ever trained.

### SageMaker Serverless Inference
The inference endpoint uses SageMaker Serverless Inference — no always-on EC2 instance, no VPC required. Charges apply only when predictions are requested. At one batch prediction job per day, the inference cost is essentially zero.

### MLB Stats API Integration
Both ingestion and inference use the official MLB Stats API — reliable, free, no scraping required. The API provides probable starters for upcoming games, making pre-game prediction possible. The query Lambda enriches stored predictions with actual game outcomes in real time by calling the same API, so the Recent Results panel updates automatically as games finish.

### Terraform Infrastructure as Code
All AWS infrastructure is defined in Terraform with S3 remote state — S3 buckets, IAM roles, Lambda functions, SageMaker pipeline, Model Registry, API Gateway, EventBridge rules, and CloudWatch log groups. The ECR repository for the prediction Lambda container image is also Terraform-managed.

### Container Image for ML Lambda
The prediction Lambda is deployed as a Docker container image rather than a zip package, because xgboost and scikit-learn exceed Lambda's 250MB unzipped package limit. The container image is built for linux/amd64 and pushed to ECR. This is a common real-world pattern for ML inference in serverless environments.

---

## Cost Profile

This project is designed to run at minimal ongoing cost:

| Resource | Monthly Cost |
|----------|-------------|
| SageMaker Pipeline (daily retraining) | ~$0.60 |
| SageMaker Serverless Endpoint | ~$0.01 |
| ECR image storage (~700MB) | ~$0.07 |
| S3 storage and requests | ~$0.05 |
| Lambda, API Gateway, EventBridge | Free tier |
| **Total** | **~$0.75/month** |

---

## Project Structure

```
mlb-game-predictions-ml-pipeline/
├── terraform/                    — complete AWS infrastructure as code
│   ├── main.tf                   — provider, backend (S3 remote state)
│   ├── variables.tf
│   ├── outputs.tf
│   ├── s3.tf                     — three S3 buckets (data, frontend, sagemaker)
│   ├── iam.tf                    — four IAM roles with least-privilege policies
│   ├── lambda.tf                 — four Lambda functions + ECR repository
│   ├── sagemaker.tf              — pipeline definition + model package group
│   ├── api_gateway.tf            — REST API with key auth and throttling
│   ├── eventbridge.tf            — daily ingestion and prediction schedules
│   └── terraform.tfvars          — not in git (contains secrets)
├── backend/
│   ├── ingestion/
│   │   └── lambda_function.py    — MLB API → S3 raw data
│   ├── pipeline_trigger/
│   │   └── lambda_function.py    — S3 event → SageMaker pipeline
│   ├── prediction/
│   │   ├── lambda_function.py    — features → SageMaker endpoint → S3
│   │   ├── Dockerfile            — container image for ML dependencies
│   │   └── requirements.txt
│   └── query/
│       └── lambda_function.py    — S3 predictions → API → frontend
├── sagemaker/
│   ├── engineer_v2.py            — feature engineering for SageMaker jobs
│   └── evaluate.py               — model evaluation and quality gate
├── src/
│   ├── features/
│   │   └── engineer_v2.py        — local feature engineering
│   ├── training/
│   │   └── train_v2.py           — local model training
│   └── inference/
│       └── predict.py            — local prediction generation
├── frontend/
│   └── src/
│       ├── App.js                — main app, data fetching, dark mode
│       ├── App.css               — CSS custom properties for light/dark
│       └── components/
│           ├── TodaysPredictions.js
│           ├── RecentResults.js
│           └── ModelMetrics.js
├── data/                         — gitignored (raw CSVs, models)
├── collect_data.py               — initial pybaseball data collection
├── collect_2026.py               — 2026 season data collection
├── collect_game_ids.py           — MLB API schedule collection
├── collect_pitching.py           — pitcher stats collection
├── deploy_ingestion.ps1          — Lambda deployment scripts (Windows)
├── deploy_pipeline_trigger.ps1
├── deploy_prediction.ps1         — builds and pushes Docker image to ECR
├── deploy_query.ps1
└── requirements.txt
```

---

## Local Development Setup

### Prerequisites

- Python 3.9+
- Node.js 18+
- AWS CLI configured with appropriate credentials
- Docker (required for prediction Lambda container image)
- Terraform 1.0+

### Python Setup

```bash
git clone https://github.com/Tickenest/mlb-game-predictions-ml-pipeline.git
cd mlb-game-predictions-ml-pipeline
python -m venv .venv
source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```
AWS_PROFILE=your-aws-profile
DATA_BUCKET=your-s3-data-bucket-name
```

### Running Feature Engineering Locally

```bash
python src/features/engineer_v2.py
```

### Running Training Locally

```bash
python src/training/train_v2.py
```

### Running Predictions Locally

```bash
python src/inference/predict.py
```

### Frontend Setup

```bash
cd frontend
npm install
```

Create `frontend/src/config.js` based on `config.example.js`. Then:

```bash
npm start
```

---

## AWS Deployment

### Prerequisites

- AWS CLI profile with appropriate permissions
- Docker running (for prediction Lambda container)
- Terraform installed

### Infrastructure

```bash
# Create S3 bucket for Terraform state first
aws s3api create-bucket --bucket your-terraform-state-bucket --region us-east-1

cd terraform
terraform init
terraform apply
```

### Lambda Deployment

```powershell
.\deploy_ingestion.ps1
.\deploy_pipeline_trigger.ps1
.\deploy_prediction.ps1   # builds and pushes Docker image to ECR
.\deploy_query.ps1
```

### Upload Initial Data

```bash
aws s3 cp data/raw_game_results.csv s3://your-data-bucket/raw/game_results.csv
aws s3 cp data/game_schedule.csv s3://your-data-bucket/raw/game_schedule.csv
aws s3 cp data/pitching_stats.csv s3://your-data-bucket/raw/pitching_stats.csv
aws s3 cp data/models/encoders_v2.pkl s3://your-data-bucket/models/encoders_v2.pkl
aws s3 cp data/models/imputer_v2.pkl s3://your-data-bucket/models/imputer_v2.pkl
aws s3 cp data/models/metrics_v2.json s3://your-data-bucket/models/metrics_v2.json
aws s3 cp sagemaker/engineer_v2.py s3://your-data-bucket/code/engineer_v2.py
aws s3 cp sagemaker/evaluate.py s3://your-data-bucket/code/evaluate.py
```

### Run the Pipeline

```bash
aws lambda invoke \
    --function-name mlb-predictions-pipeline-trigger \
    --payload '{"date": "today"}' \
    response.json
```

### Frontend Deployment

```bash
cd frontend
npm run build
aws s3 sync build/ s3://your-frontend-bucket
```

---

## Known Notes

- The SageMaker pipeline uses step caching with a 1-hour TTL — back-to-back runs within an hour will reuse previous step outputs
- Probable pitcher data from the MLB Stats API is available for most games but may show as TBD for some matchups, particularly early in the day
- The model retrains daily but the SageMaker serverless endpoint must be manually updated when a new model is approved in the Model Registry — endpoint update automation is a planned improvement
- pybaseball's `team_results.py` requires a one-line patch for Python 3.9+ compatibility: change `inplace=True` to a direct assignment on the Attendance column

---

## Built By

[Tickenest](https://github.com/Tickenest)
