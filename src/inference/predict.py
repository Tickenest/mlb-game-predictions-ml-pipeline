import pandas as pd
import numpy as np
import pickle
import json
import requests
import unicodedata
from pathlib import Path
from datetime import date, datetime

MODEL_PATH = Path("data/models/xgb_model_v2.pkl")
ENCODERS_PATH = Path("data/models/encoders_v2.pkl")
IMPUTER_PATH = Path("data/models/imputer_v2.pkl")
PITCHING_PATH = Path("data/pitching_stats.csv")
RAW_DATA_PATH = Path("data/raw_game_results.csv")

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

ROLLING_WINDOW = 15

# Team name to abbreviation mapping
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


def normalize_name(name: str) -> str:
    """Normalize pitcher name — strip accents, lowercase."""
    if pd.isna(name) or name is None:
        return None
    nfkd = unicodedata.normalize('NFKD', str(name))
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_name.lower().strip()


def load_models():
    """Load trained model, encoders, and imputer."""
    with open(MODEL_PATH, 'rb') as f:
        model = pickle.load(f)
    with open(ENCODERS_PATH, 'rb') as f:
        encoders = pickle.load(f)
    with open(IMPUTER_PATH, 'rb') as f:
        imputer = pickle.load(f)
    return model, encoders, imputer


def get_todays_games(target_date: str = None) -> list[dict]:
    """Fetch today's games and probable starters from MLB API."""
    if target_date is None:
        target_date = date.today().isoformat()

    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "date": target_date,
        "sportId": 1,
        "hydrate": "probablePitcher,linescore",
        "gameType": "R",
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    games = []
    for date_entry in data.get('dates', []):
        for game in date_entry.get('games', []):
            status = game['status']['detailedState']
            if status in ('Postponed', 'Cancelled'):
                continue

            game_time = game.get('gameDate', '')
            try:
                dt = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
                # Convert to ET (UTC-4 during EDT)
                hour_et = (dt.hour - 4) % 24
                is_day = 1 if hour_et < 17 else 0
            except Exception:
                is_day = 0

            games.append({
                'game_pk': game['gamePk'],
                'date': target_date,
                'home_team_full': game['teams']['home']['team']['name'],
                'away_team_full': game['teams']['away']['team']['name'],
                'home_team': NAME_TO_ABBREV.get(
                    game['teams']['home']['team']['name'], 
                    game['teams']['home']['team'].get('abbreviation', 'UNK')
                ),
                'away_team': NAME_TO_ABBREV.get(
                    game['teams']['away']['team']['name'],
                    game['teams']['away']['team'].get('abbreviation', 'UNK')
                ),
                'home_pitcher': game['teams']['home'].get(
                    'probablePitcher', {}
                ).get('fullName', None),
                'away_pitcher': game['teams']['away'].get(
                    'probablePitcher', {}
                ).get('fullName', None),
                'status': status,
                'is_day': is_day,
                'month': int(target_date[5:7]),
            })

    return games


def compute_rolling_stats(team: str, as_of_date: str,
                           is_home: bool) -> dict:
    """Compute rolling team stats from raw game results up to as_of_date."""
    df = pd.read_csv(RAW_DATA_PATH)
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
    df['date'] = pd.to_datetime(df['date_str'], format='mixed', errors='coerce')

    # Filter to this team's games before the target date
    team_df = df[
        (df['Tm'] == team) &
        (df['date'] < pd.to_datetime(as_of_date))
    ].sort_values('date').tail(ROLLING_WINDOW)

    if len(team_df) < 5:
        return {}

    stats = {
        'rolling_win_rate': team_df['win'].mean(),
        'rolling_runs_scored': team_df['R'].mean(),
        'rolling_runs_allowed': team_df['RA'].mean(),
        'rolling_run_diff': team_df['run_diff'].mean(),
    }

    # Home or away specific win rate
    if is_home:
        home_games = team_df[team_df['is_home'] == 1]
        stats['rolling_home_win_rate'] = (
            home_games['win'].mean() if len(home_games) >= 3 else stats['rolling_win_rate']
        )
    else:
        away_games = team_df[team_df['is_home'] == 0]
        stats['rolling_away_win_rate'] = (
            away_games['win'].mean() if len(away_games) >= 3 else stats['rolling_win_rate']
        )

    return stats


def get_pitcher_stats(pitcher_name: str, season: int,
                      pitching_df: pd.DataFrame) -> dict:
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
        'era': row.get('ERA', None),
        'whip': row.get('WHIP', None),
        'so9': row.get('SO9', None),
    }


def build_prediction_row(game: dict, pitching_df: pd.DataFrame,
                          encoders: dict) -> dict:
    """Build a feature row for one game."""
    target_date = game['date']
    season = int(target_date[:4])

    # Rolling team stats
    home_stats = compute_rolling_stats(game['home_team'], target_date, is_home=True)
    away_stats = compute_rolling_stats(game['away_team'], target_date, is_home=False)

    # Pitcher stats
    home_pitcher = get_pitcher_stats(game['home_pitcher'], season, pitching_df)
    away_pitcher = get_pitcher_stats(game['away_pitcher'], season, pitching_df)

    # Encode teams
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


def predict(target_date: str = None) -> list[dict]:
    """Generate predictions for all games on a given date."""
    if target_date is None:
        target_date = date.today().isoformat()

    print(f"Generating predictions for {target_date}...")

    model, encoders, imputer = load_models()

    pitching_df = pd.read_csv(PITCHING_PATH)
    pitching_df['pitcher_norm'] = pitching_df['Name'].apply(normalize_name)
    for col in ['ERA', 'WHIP', 'SO9']:
        pitching_df[col] = pd.to_numeric(pitching_df[col], errors='coerce')
    pitching_df['ERA'] = pitching_df['ERA'].clip(upper=15)

    games = get_todays_games(target_date)
    print(f"  Found {len(games)} games")

    if not games:
        print("  No games found.")
        return []

    predictions = []
    for game in games:
        print(f"  Processing {game['away_team_full']} @ {game['home_team_full']}...")

        row = build_prediction_row(game, pitching_df, encoders)
        X = pd.DataFrame([row])[FEATURE_COLS]
        X_imp = imputer.transform(X)
        prob = model.predict_proba(X_imp)[0]

        predictions.append({
            'date': target_date,
            'game_pk': game['game_pk'],
            'home_team': game['home_team_full'],
            'away_team': game['away_team_full'],
            'home_team_abbrev': game['home_team'],
            'away_team_abbrev': game['away_team'],
            'home_pitcher': game['home_pitcher'] or 'TBD',
            'away_pitcher': game['away_pitcher'] or 'TBD',
            'home_win_probability': round(float(prob[1]), 4),
            'away_win_probability': round(float(prob[0]), 4),
            'predicted_winner': game['home_team_full'] if prob[1] > 0.5 else game['away_team_full'],
            'confidence': round(float(max(prob)), 4),
            'status': game['status'],
        })

    return predictions


if __name__ == "__main__":
    preds = predict()
    print(f"\n=== Predictions for Today ===")
    for p in preds:
        print(f"\n{p['away_team']} @ {p['home_team']}")
        print(f"  Starters: {p['away_pitcher']} vs {p['home_pitcher']}")
        print(f"  Home win probability: {p['home_win_probability']:.1%}")
        print(f"  Away win probability: {p['away_win_probability']:.1%}")
        print(f"  Predicted winner: {p['predicted_winner']} ({p['confidence']:.1%} confidence)")