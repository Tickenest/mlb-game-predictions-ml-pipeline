import json
import os
import boto3
import io
import pickle
import unicodedata
import requests
import pandas as pd
import numpy as np
from datetime import date
from sklearn.impute import SimpleImputer

S3_CLIENT = boto3.client('s3')
SAGEMAKER_RUNTIME = boto3.client('sagemaker-runtime')
DATA_BUCKET = os.environ.get('DATA_BUCKET')
SAGEMAKER_ENDPOINT = os.environ.get('SAGEMAKER_ENDPOINT', 'mlb-predictions-serverless-endpoint')

ROLLING_WINDOW = 15
FEATURE_COLS = [
    'month', 'is_day',
    'home_team_enc', 'away_team_enc',
    'home_rolling_win_rate',
    'home_rolling_runs_scored',
    'home_rolling_runs_allowed',
    'home_rolling_run_diff',
    'home_rolling_home_win_rate',
    'away_rolling_win_rate',
    'away_rolling_runs_scored',
    'away_rolling_runs_allowed',
    'away_rolling_run_diff',
    'away_rolling_away_win_rate',
    'home_starter_era',
    'home_starter_whip',
    'home_starter_so9',
    'away_starter_era',
    'away_starter_whip',
    'away_starter_so9',
]

NAME_TO_ABBREV = {
    'Arizona Diamondbacks': 'ARI', 'Atlanta Braves': 'ATL',
    'Baltimore Orioles': 'BAL', 'Boston Red Sox': 'BOS',
    'Chicago Cubs': 'CHC', 'Chicago White Sox': 'CHW',
    'Cincinnati Reds': 'CIN', 'Cleveland Guardians': 'CLE',
    'Colorado Rockies': 'COL', 'Detroit Tigers': 'DET',
    'Houston Astros': 'HOU', 'Kansas City Royals': 'KCR',
    'Los Angeles Angels': 'LAA', 'Los Angeles Dodgers': 'LAD',
    'Miami Marlins': 'MIA', 'Milwaukee Brewers': 'MIL',
    'Minnesota Twins': 'MIN', 'New York Mets': 'NYM',
    'New York Yankees': 'NYY', 'Athletics': 'ATH',
    'Oakland Athletics': 'ATH',
    'Philadelphia Phillies': 'PHI', 'Pittsburgh Pirates': 'PIT',
    'San Diego Padres': 'SDP', 'San Francisco Giants': 'SFG',
    'Seattle Mariners': 'SEA', 'St. Louis Cardinals': 'STL',
    'Tampa Bay Rays': 'TBR', 'Texas Rangers': 'TEX',
    'Toronto Blue Jays': 'TOR', 'Washington Nationals': 'WSN',
    'Cleveland Indians': 'CLE',
}


def normalize_name(name):
    if pd.isna(name) or name is None:
        return None
    nfkd = unicodedata.normalize('NFKD', str(name))
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_name.lower().strip()


def load_artifacts():
    """Load encoders and imputer from S3."""
    artifacts = {}
    for name, key in [
        ('encoders', 'models/encoders_v2.pkl'),
        ('imputer', 'models/imputer_v2.pkl'),
    ]:
        response = S3_CLIENT.get_object(Bucket=DATA_BUCKET, Key=key)
        artifacts[name] = pickle.loads(response['Body'].read())
    return artifacts['encoders'], artifacts['imputer']


def load_raw_data():
    """Load raw game results from S3."""
    response = S3_CLIENT.get_object(Bucket=DATA_BUCKET, Key='raw/game_results.csv')
    df = pd.read_csv(io.BytesIO(response['Body'].read()))
    return df


def load_pitching_stats():
    """Load pitcher seasonal stats from S3."""
    response = S3_CLIENT.get_object(Bucket=DATA_BUCKET, Key='raw/pitching_stats.csv')
    df = pd.read_csv(io.BytesIO(response['Body'].read()))
    df['pitcher_norm'] = df['Name'].apply(normalize_name)
    for col in ['ERA', 'WHIP', 'SO9']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['ERA'] = df['ERA'].clip(upper=15)
    return df


def get_todays_games(target_date):
    """Fetch today's games and probable starters from MLB API."""
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "date": target_date,
        "sportId": 1,
        "hydrate": "probablePitcher,linescore",
        "gameType": "R",
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    games = []
    for date_entry in data.get('dates', []):
        for game in date_entry.get('games', []):
            status = game['status']['detailedState']
            if status in ('Postponed', 'Cancelled'):
                continue

            home = game['teams']['home']
            away = game['teams']['away']

            games.append({
                'game_pk': game['gamePk'],
                'date': target_date,
                'home_team_full': home['team']['name'],
                'away_team_full': away['team']['name'],
                'home_team': NAME_TO_ABBREV.get(
                    home['team']['name'],
                    home['team'].get('abbreviation', 'UNK')
                ),
                'away_team': NAME_TO_ABBREV.get(
                    away['team']['name'],
                    away['team'].get('abbreviation', 'UNK')
                ),
                'home_pitcher': home.get('probablePitcher', {}).get('fullName'),
                'away_pitcher': away.get('probablePitcher', {}).get('fullName'),
                'status': status,
                'is_day': 0,
                'month': int(target_date[5:7]),
            })
    return games


def compute_rolling_stats(raw_df, team, as_of_date, is_home):
    """Compute rolling team stats from raw data."""
    df = raw_df.copy()
    df = df[df['W/L'].isin(['W', 'L', 'W-wo', 'L-wo'])].copy()
    df['win'] = df['W/L'].isin(['W', 'W-wo']).astype(int)
    df['is_home'] = (df['Home_Away'] == 'Home').astype(int)
    df['R'] = pd.to_numeric(df['R'], errors='coerce')
    df['RA'] = pd.to_numeric(df['RA'], errors='coerce')
    df['run_diff'] = df['R'] - df['RA']

    df['date_clean'] = df['Date'].str.replace(r'\s*\(\d\)$', '', regex=True)
    df['date_str'] = df['date_clean'].str.extract(
        r'(\w+ \d+)$'
    )[0] + ' ' + df['season'].astype(str)
    df['date'] = pd.to_datetime(df['date_str'], format='%b %d %Y', errors='coerce')
    mask = df['date'].isna()
    if mask.any():
        df.loc[mask, 'date'] = pd.to_datetime(
            df.loc[mask, 'date_str'], errors='coerce'
        )

    team_df = df[
        (df['Tm'] == team) &
        (df['date'] < pd.to_datetime(as_of_date))
    ].sort_values('date').tail(ROLLING_WINDOW)

    if len(team_df) < 5:
        return {}

    team_df['run_diff'] = team_df['R'] - team_df['RA']
    stats = {
        'rolling_win_rate': team_df['win'].mean(),
        'rolling_runs_scored': team_df['R'].mean(),
        'rolling_runs_allowed': team_df['RA'].mean(),
        'rolling_run_diff': team_df['run_diff'].mean(),
    }

    if is_home:
        home_g = team_df[team_df['is_home'] == 1]
        stats['rolling_home_win_rate'] = (
            home_g['win'].mean() if len(home_g) >= 3 else stats['rolling_win_rate']
        )
    else:
        away_g = team_df[team_df['is_home'] == 0]
        stats['rolling_away_win_rate'] = (
            away_g['win'].mean() if len(away_g) >= 3 else stats['rolling_win_rate']
        )

    return stats


def get_pitcher_stats(pitcher_name, season, pitching_df):
    """Look up pitcher seasonal stats."""
    norm = normalize_name(pitcher_name)
    match = pitching_df[
        (pitching_df['pitcher_norm'] == norm) &
        (pitching_df['season'] == season)
    ]
    if match.empty:
        return {'era': None, 'whip': None, 'so9': None}
    row = match.iloc[0]
    return {
        'era': row.get('ERA'),
        'whip': row.get('WHIP'),
        'so9': row.get('SO9'),
    }


def build_feature_row(game, raw_df, pitching_df, encoders):
    """Build a feature dict for one game."""
    target_date = game['date']
    season = int(target_date[:4])

    home_stats = compute_rolling_stats(
        raw_df, game['home_team'], target_date, is_home=True
    )
    away_stats = compute_rolling_stats(
        raw_df, game['away_team'], target_date, is_home=False
    )
    home_pitcher = get_pitcher_stats(game['home_pitcher'], season, pitching_df)
    away_pitcher = get_pitcher_stats(game['away_pitcher'], season, pitching_df)

    try:
        home_enc = encoders['home_team'].transform([game['home_team']])[0]
    except ValueError:
        home_enc = -1
    try:
        away_enc = encoders['away_team'].transform([game['away_team']])[0]
    except ValueError:
        away_enc = -1

    return {
        'month': game['month'],
        'is_day': game['is_day'],
        'home_team_enc': home_enc,
        'away_team_enc': away_enc,
        'home_rolling_win_rate': home_stats.get('rolling_win_rate'),
        'home_rolling_runs_scored': home_stats.get('rolling_runs_scored'),
        'home_rolling_runs_allowed': home_stats.get('rolling_runs_allowed'),
        'home_rolling_run_diff': home_stats.get('rolling_run_diff'),
        'home_rolling_home_win_rate': home_stats.get('rolling_home_win_rate'),
        'away_rolling_win_rate': away_stats.get('rolling_win_rate'),
        'away_rolling_runs_scored': away_stats.get('rolling_runs_scored'),
        'away_rolling_runs_allowed': away_stats.get('rolling_runs_allowed'),
        'away_rolling_run_diff': away_stats.get('rolling_run_diff'),
        'away_rolling_away_win_rate': away_stats.get('rolling_away_win_rate'),
        'home_starter_era': home_pitcher['era'],
        'home_starter_whip': home_pitcher['whip'],
        'home_starter_so9': home_pitcher['so9'],
        'away_starter_era': away_pitcher['era'],
        'away_starter_whip': away_pitcher['whip'],
        'away_starter_so9': away_pitcher['so9'],
    }


def invoke_endpoint(feature_row, imputer):
    """Send features to SageMaker serverless endpoint."""
    X = pd.DataFrame([feature_row])[FEATURE_COLS]
    X_imp = imputer.transform(X)
    csv_row = ','.join([str(v) for v in X_imp[0]])

    response = SAGEMAKER_RUNTIME.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT,
        ContentType='text/csv',
        Body=csv_row.encode('ascii')
    )

    prob = float(response['Body'].read().decode('utf-8').strip())
    return prob


def lambda_handler(event, context):
    """Generate predictions for today's games."""
    target_date = event.get('date', date.today().isoformat())
    print(f"Generating predictions for {target_date}...")

    print("Loading artifacts...")
    encoders, imputer = load_artifacts()

    print("Loading raw data...")
    raw_df = load_raw_data()

    print("Loading pitching stats...")
    pitching_df = load_pitching_stats()

    print("Fetching today's games...")
    games = get_todays_games(target_date)
    print(f"Found {len(games)} games")

    predictions = []
    for game in games:
        print(f"  {game['away_team_full']} @ {game['home_team_full']}...")
        row = build_feature_row(game, raw_df, pitching_df, encoders)
        home_prob = invoke_endpoint(row, imputer)
        away_prob = round(1.0 - home_prob, 4)
        home_prob = round(home_prob, 4)

        predictions.append({
            'date': target_date,
            'game_pk': game['game_pk'],
            'home_team': game['home_team_full'],
            'away_team': game['away_team_full'],
            'home_team_abbrev': game['home_team'],
            'away_team_abbrev': game['away_team'],
            'home_pitcher': game['home_pitcher'] or 'TBD',
            'away_pitcher': game['away_pitcher'] or 'TBD',
            'home_win_probability': home_prob,
            'away_win_probability': away_prob,
            'predicted_winner': (
                game['home_team_full'] if home_prob > 0.5 else game['away_team_full']
            ),
            'confidence': round(float(max(home_prob, away_prob)), 4),
        })

    key = f"predictions/{target_date}.json"
    S3_CLIENT.put_object(
        Bucket=DATA_BUCKET,
        Key=key,
        Body=json.dumps(predictions),
        ContentType='application/json'
    )
    print(f"Saved {len(predictions)} predictions to s3://{DATA_BUCKET}/{key}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Generated {len(predictions)} predictions for {target_date}',
            'predictions': predictions,
        })
    }