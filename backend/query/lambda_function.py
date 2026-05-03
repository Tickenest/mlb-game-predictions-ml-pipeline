import json
import os
import boto3
import requests
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
    except Exception:
        return []


def get_actual_results(target_date: str) -> dict:
    """
    Fetch actual game results from MLB API.
    Returns dict of game_pk -> winning team full name.
    """
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "date": target_date,
        "sportId": 1,
        "hydrate": "linescore",
        "gameType": "R",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return {}

    results = {}
    for date_entry in data.get('dates', []):
        for game in date_entry.get('games', []):
            if game['status']['detailedState'] != 'Final':
                continue
            game_pk = game['gamePk']
            home = game['teams']['home']
            away = game['teams']['away']
            home_score = home.get('score', 0)
            away_score = away.get('score', 0)
            if home_score > away_score:
                results[game_pk] = home['team']['name']
            else:
                results[game_pk] = away['team']['name']

    return results


def enrich_with_results(predictions: list[dict],
                         actual_results: dict) -> list[dict]:
    """Add result field to each prediction."""
    enriched = []
    for pred in predictions:
        game_pk = pred.get('game_pk')
        actual_winner = actual_results.get(game_pk)
        if actual_winner is None:
            pred['result'] = 'pending'
            pred['actual_winner'] = None
        elif actual_winner == pred['predicted_winner']:
            pred['result'] = 'correct'
            pred['actual_winner'] = actual_winner
        else:
            pred['result'] = 'incorrect'
            pred['actual_winner'] = actual_winner
        enriched.append(pred)
    return enriched


def load_recent_predictions(days: int = 7) -> list[dict]:
    """Load and enrich predictions for the last N days."""
    all_predictions = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        preds = load_predictions(d)
        if preds:
            actual = get_actual_results(d)
            preds = enrich_with_results(preds, actual)
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
            preds = load_predictions(target_date)
            actual = get_actual_results(target_date)
            preds = enrich_with_results(preds, actual)
            return {
                'statusCode': 200,
                'headers': cors_headers(),
                'body': json.dumps({
                    'query_type': query_type,
                    'date': target_date,
                    'data': preds
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