import json
import os
import boto3
import io
import pandas as pd
from datetime import date, timedelta

S3_CLIENT = boto3.client('s3')
DATA_BUCKET = os.environ.get('DATA_BUCKET')
PREDICTIONS_KEY_PREFIX = 'predictions/'
METRICS_KEY = 'models/metrics_v2.json'


def cors_headers() -> dict:
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Api-Key',
        'Access-Control-Allow-Methods': 'POST,OPTIONS',
        'Content-Type': 'application/json',
    }


def load_predictions(target_date: str) -> list[dict]:
    """Load predictions for a given date from S3."""
    key = f"{PREDICTIONS_KEY_PREFIX}{target_date}.json"
    try:
        response = S3_CLIENT.get_object(Bucket=DATA_BUCKET, Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except S3_CLIENT.exceptions.NoSuchKey:
        return []
    except Exception as e:
        print(f"Error loading predictions: {e}")
        return []


def load_recent_predictions(days: int = 7) -> list[dict]:
    """Load predictions for the last N days."""
    all_predictions = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        preds = load_predictions(d)
        all_predictions.extend(preds)
    return all_predictions


def load_metrics() -> dict:
    """Load model metrics from S3."""
    try:
        response = S3_CLIENT.get_object(Bucket=DATA_BUCKET, Key=METRICS_KEY)
        return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        print(f"Error loading metrics: {e}")
        return {}


def lambda_handler(event, context):
    """Query Lambda — serves predictions and model metrics to frontend."""
    try:
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)

        query_type = body.get('query_type')
        params = body.get('params', {})

        if not query_type:
            return {
                'statusCode': 400,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'query_type is required'})
            }

        if query_type == 'todays_predictions':
            target_date = params.get('date', date.today().isoformat())
            data = load_predictions(target_date)
            return {
                'statusCode': 200,
                'headers': cors_headers(),
                'body': json.dumps({
                    'query_type': query_type,
                    'date': target_date,
                    'data': data
                })
            }

        elif query_type == 'recent_predictions':
            days = params.get('days', 7)
            data = load_recent_predictions(days)
            return {
                'statusCode': 200,
                'headers': cors_headers(),
                'body': json.dumps({
                    'query_type': query_type,
                    'data': data
                })
            }

        elif query_type == 'model_metrics':
            data = load_metrics()
            return {
                'statusCode': 200,
                'headers': cors_headers(),
                'body': json.dumps({
                    'query_type': query_type,
                    'data': data
                })
            }

        else:
            return {
                'statusCode': 400,
                'headers': cors_headers(),
                'body': json.dumps({'error': f'Unknown query_type: {query_type}'})
            }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': cors_headers(),
            'body': json.dumps({'error': str(e)})
        }