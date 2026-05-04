import json
import os
import boto3
import requests
import pandas as pd
import io
from datetime import date, timedelta

S3_CLIENT = boto3.client('s3')
DATA_BUCKET = os.environ.get('DATA_BUCKET')
RAW_KEY = 'raw/game_results.csv'

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


def get_completed_games(target_date: str) -> list[dict]:
    """Fetch completed games for a given date from MLB Stats API."""
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
            if game['status']['detailedState'] != 'Final':
                continue

            home = game['teams']['home']
            away = game['teams']['away']

            home_score = home.get('score', None)
            away_score = away.get('score', None)
            home_won = home_score > away_score if (
                home_score is not None and away_score is not None
            ) else None

            home_abbrev = NAME_TO_ABBREV.get(
                home['team']['name'],
                home['team'].get('abbreviation', 'UNK')
            )
            away_abbrev = NAME_TO_ABBREV.get(
                away['team']['name'],
                away['team'].get('abbreviation', 'UNK')
            )

            home_pitcher = home.get('probablePitcher', {}).get('fullName', None)
            away_pitcher = away.get('probablePitcher', {}).get('fullName', None)

            games.append({
                'game_pk': game['gamePk'],
                'date': target_date,
                'season': int(target_date[:4]),
                'home_team': home_abbrev,
                'away_team': away_abbrev,
                'home_team_full': home['team']['name'],
                'away_team_full': away['team']['name'],
                'home_score': home_score,
                'away_score': away_score,
                'home_win': int(home_won) if home_won is not None else None,
                'home_pitcher': home_pitcher,
                'away_pitcher': away_pitcher,
                'status': game['status']['detailedState'],
            })

    return games


def load_existing_data() -> pd.DataFrame:
    """Load existing game results from S3."""
    try:
        response = S3_CLIENT.get_object(Bucket=DATA_BUCKET, Key=RAW_KEY)
        df = pd.read_csv(io.BytesIO(response['Body'].read()))
        print(f"Loaded {len(df)} existing rows from S3")
        return df
    except S3_CLIENT.exceptions.NoSuchKey:
        print("No existing data found — starting fresh")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading existing data: {e}")
        return pd.DataFrame()


def save_data(df: pd.DataFrame) -> None:
    """Save game results back to S3."""
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    S3_CLIENT.put_object(
        Bucket=DATA_BUCKET,
        Key=RAW_KEY,
        Body=buffer.getvalue(),
        ContentType='text/csv'
    )
    print(f"Saved {len(df)} rows to s3://{DATA_BUCKET}/{RAW_KEY}")


def lambda_handler(event, context):
    """
    Fetch yesterday's MLB game results and append to S3.
    Triggered daily by EventBridge.
    """
    # Determine target date — yesterday by default
    target_date = event.get('date', (date.today() - timedelta(days=1)).isoformat())
    print(f"Fetching games for {target_date}...")

    # Fetch completed games
    games = get_completed_games(target_date)
    print(f"Found {len(games)} completed games")

    if not games:
        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'No completed games found for {target_date}'})
        }

    # Load existing data
    existing = load_existing_data()

    # Convert new games to DataFrame
    new_df = pd.DataFrame(games)

    # Append new data avoiding duplicates on game_pk
    if not existing.empty:
        if 'game_pk' in existing.columns:
            existing_pks = set(existing['game_pk'].astype(str))
            new_df = new_df[~new_df['game_pk'].astype(str).isin(existing_pks)]
            print(f"New unique games to add: {len(new_df)}")
            combined = pd.concat([existing, new_df], ignore_index=True)
        else:
            print("WARNING: Existing data missing game_pk column — appending all new games")
            combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    # Save back to S3
    save_data(combined)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Successfully processed {len(new_df)} new games for {target_date}',
            'total_rows': len(combined),
            'new_rows': len(new_df),
        })
    }


if __name__ == "__main__":
    # Local test
    import sys
    test_date = sys.argv[1] if len(sys.argv) > 1 else (
        date.today() - timedelta(days=1)
    ).isoformat()
    result = get_completed_games(test_date)
    print(f"\nGames for {test_date}:")
    for g in result:
        print(f"  {g['away_team']} @ {g['home_team']}: "
              f"{g['away_score']}-{g['home_score']} "
              f"({'Home Win' if g['home_win'] else 'Away Win'})")