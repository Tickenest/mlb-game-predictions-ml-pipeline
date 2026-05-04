import pandas as pd
import numpy as np
import unicodedata
import os
import json
from pathlib import Path
from sklearn.preprocessing import LabelEncoder

# SageMaker paths
INPUT_RAW = Path("/opt/ml/processing/input/raw")
OUTPUT_PATH = Path("/opt/ml/processing/output")

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

TARGET_COL = 'home_win'

def parse_dates(date_series):
    """Parse dates trying multiple formats — works across all pandas versions."""
    result = pd.to_datetime(date_series, format='%b %d %Y', errors='coerce')
    # Fill any that failed with a second attempt
    mask = result.isna()
    if mask.any():
        result[mask] = pd.to_datetime(date_series[mask], errors='coerce')
    return result

def normalize_name(name):
    if pd.isna(name):
        return name
    nfkd = unicodedata.normalize('NFKD', str(name))
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_name.lower().strip()


def parse_dates(date_series):
    """Parse dates trying multiple formats — works across all pandas versions."""
    result = pd.to_datetime(date_series, format='%b %d %Y', errors='coerce')
    mask = result.isna()
    if mask.any():
        result[mask] = pd.to_datetime(date_series[mask], errors='coerce')
    return result


def load_and_clean(path):
    df = pd.read_csv(path)
    df = df[df['W/L'].isin(['W', 'L', 'W-wo', 'L-wo'])].copy()
    df['win'] = df['W/L'].isin(['W', 'W-wo']).astype(int)
    df['is_home'] = (df['Home_Away'] == 'Home').astype(int)
    df['is_day'] = (df['D/N'] == 'D').astype(int)
    df['R'] = pd.to_numeric(df['R'], errors='coerce')
    df['RA'] = pd.to_numeric(df['RA'], errors='coerce')
    df['run_diff'] = df['R'] - df['RA']

    df['date_clean'] = df['Date'].str.replace(r'\s*\(\d\)$', '', regex=True)
    df['date_str'] = df['date_clean'].str.extract(r'(\w+ \d+)$')[0] + ' ' + df['season'].astype(str)

    # Parse dates in a way that works across all pandas versions
    df['date'] = parse_dates(df['date_str']).dt.strftime('%Y-%m-%d')
    df['month'] = pd.to_datetime(df['date'], errors='coerce').dt.month
    df['game_num'] = df['Date'].str.extract(r'\((\d)\)$')[0].fillna('1')

    drop_cols = ['W/L', 'Home_Away', 'Inn', 'W-L', 'Rank', 'GB', 'Win',
                 'Loss', 'Save', 'Time', 'D/N', 'Attendance', 'cLI',
                 'Streak', 'Orig. Scheduled', 'date_str', 'Date', 'date_clean']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])
    df = df.sort_values(['Tm', 'date']).reset_index(drop=True)
    return df


def add_rolling_features(df, window=ROLLING_WINDOW):
    df = df.copy()
    for col, new_col in [
        ('win', 'rolling_win_rate'),
        ('R', 'rolling_runs_scored'),
        ('RA', 'rolling_runs_allowed'),
        ('run_diff', 'rolling_run_diff'),
    ]:
        df[new_col] = (
            df.groupby('Tm')[col]
            .transform(lambda x: x.shift(1).rolling(window, min_periods=5).mean())
        )

    home_wins = df[df['is_home'] == 1].copy()
    home_win_rate = (
        home_wins.groupby('Tm')['win']
        .transform(lambda x: x.shift(1).rolling(window, min_periods=3).mean())
    )
    df.loc[df['is_home'] == 1, 'rolling_home_win_rate'] = home_win_rate

    away_games = df[df['is_home'] == 0].copy()
    away_win_rate = (
        away_games.groupby('Tm')['win']
        .transform(lambda x: x.shift(1).rolling(window, min_periods=3).mean())
    )
    df.loc[df['is_home'] == 0, 'rolling_away_win_rate'] = away_win_rate

    return df


def load_schedule(path):
    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d')
    df['home_pitcher_norm'] = df['home_probable'].apply(normalize_name)
    df['away_pitcher_norm'] = df['away_probable'].apply(normalize_name)
    df['season'] = df['season'].astype(str)
    return df


def load_pitching(path):
    df = pd.read_csv(path)
    df['pitcher_norm'] = df['Name'].apply(normalize_name)
    for col in ['ERA', 'WHIP', 'SO9']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['ERA'] = df['ERA'].clip(upper=15)
    df['IP'] = pd.to_numeric(df['IP'], errors='coerce')
    df['GS'] = pd.to_numeric(df['GS'], errors='coerce').fillna(0)
    df['team_primary'] = df['Tm'].str.split(',').str[0].str.strip()
    df['season'] = df['season'].astype(str)  # Add this line
    return df


def build_game_features(df, schedule, pitching):
    home = df[df['is_home'] == 1].copy()
    away = df[df['is_home'] == 0].copy()

    home = home.rename(columns={
        'Tm': 'home_team', 'Opp': 'away_team', 'win': 'home_win',
        'rolling_win_rate': 'home_rolling_win_rate',
        'rolling_runs_scored': 'home_rolling_runs_scored',
        'rolling_runs_allowed': 'home_rolling_runs_allowed',
        'rolling_run_diff': 'home_rolling_run_diff',
        'rolling_home_win_rate': 'home_rolling_home_win_rate',
    })

    away = away.rename(columns={
        'Tm': 'away_team_check',
        'rolling_win_rate': 'away_rolling_win_rate',
        'rolling_runs_scored': 'away_rolling_runs_scored',
        'rolling_runs_allowed': 'away_rolling_runs_allowed',
        'rolling_run_diff': 'away_rolling_run_diff',
        'rolling_away_win_rate': 'away_rolling_away_win_rate',
    })

    away_cols = [
        'away_team_check', 'date', 'season', 'game_num',
        'away_rolling_win_rate', 'away_rolling_runs_scored',
        'away_rolling_runs_allowed', 'away_rolling_run_diff',
        'away_rolling_away_win_rate',
    ]
    away = away[away_cols]

    home['season'] = home['season'].astype(str)
    home['game_num'] = home['game_num'].astype(str)
    home['date'] = home['date'].astype(str)
    away['season'] = away['season'].astype(str)
    away['game_num'] = away['game_num'].astype(str)
    away['date'] = away['date'].astype(str)

    print(f"  Home games before merge: {len(home)}")
    print(f"  Away games before merge: {len(away)}")
    print(f"  Home date dtype: {home['date'].dtype}")
    print(f"  Away date dtype: {away['date'].dtype}")
    print(f"  Home season dtype: {home['season'].dtype}")
    print(f"  Away season dtype: {away['season'].dtype}")
    print(f"  Home game_num dtype: {home['game_num'].dtype}")
    print(f"  Away game_num dtype: {away['game_num'].dtype}")

    games = home.merge(
        away,
        left_on=['away_team', 'date', 'season', 'game_num'],
        right_on=['away_team_check', 'date', 'season', 'game_num'],
        how='inner'
    )

    print(f"  Games after merge: {len(games)}")
    games = games.drop(columns=['away_team_check'])

    abbrev_map = {
        'ARI': 'Arizona Diamondbacks', 'ATL': 'Atlanta Braves',
        'BAL': 'Baltimore Orioles', 'BOS': 'Boston Red Sox',
        'CHC': 'Chicago Cubs', 'CHW': 'Chicago White Sox',
        'CIN': 'Cincinnati Reds', 'CLE': 'Cleveland Guardians',
        'COL': 'Colorado Rockies', 'DET': 'Detroit Tigers',
        'HOU': 'Houston Astros', 'KCR': 'Kansas City Royals',
        'LAA': 'Los Angeles Angels', 'LAD': 'Los Angeles Dodgers',
        'MIA': 'Miami Marlins', 'MIL': 'Milwaukee Brewers',
        'MIN': 'Minnesota Twins', 'NYM': 'New York Mets',
        'NYY': 'New York Yankees', 'ATH': 'Athletics',
        'OAK': 'Oakland Athletics',
        'PHI': 'Philadelphia Phillies', 'PIT': 'Pittsburgh Pirates',
        'SDP': 'San Diego Padres', 'SFG': 'San Francisco Giants',
        'SEA': 'Seattle Mariners', 'STL': 'St. Louis Cardinals',
        'TBR': 'Tampa Bay Rays', 'TEX': 'Texas Rangers',
        'TOR': 'Toronto Blue Jays', 'WSN': 'Washington Nationals',
    }

    games['home_team_full'] = games['home_team'].map(abbrev_map)
    games['away_team_full'] = games['away_team'].map(abbrev_map)

    schedule_slim = schedule[[
        'date', 'home_team', 'away_team',
        'home_pitcher_norm', 'away_pitcher_norm', 'season'
    ]].copy()

    schedule_slim['date'] = schedule_slim['date'].astype(str)
    schedule_slim['season'] = schedule_slim['season'].astype(str)

    games = games.merge(
        schedule_slim,
        left_on=['date', 'home_team_full', 'season'],
        right_on=['date', 'home_team', 'season'],
        how='left',
        suffixes=('', '_sched')
    )
    games = games.drop(
        columns=[c for c in games.columns if c.endswith('_sched')],
        errors='ignore'
    )

    starters = pitching[pitching['GS'] > 0].copy()

    games = games.merge(
        starters.rename(columns={
            'pitcher_norm': 'home_pitcher_norm',
            'ERA': 'home_starter_era',
            'WHIP': 'home_starter_whip',
            'SO9': 'home_starter_so9',
        })[['home_pitcher_norm', 'season',
            'home_starter_era', 'home_starter_whip', 'home_starter_so9']],
        on=['home_pitcher_norm', 'season'],
        how='left'
    )

    games = games.merge(
        starters.rename(columns={
            'pitcher_norm': 'away_pitcher_norm',
            'ERA': 'away_starter_era',
            'WHIP': 'away_starter_whip',
            'SO9': 'away_starter_so9',
        })[['away_pitcher_norm', 'season',
            'away_starter_era', 'away_starter_whip', 'away_starter_so9']],
        on=['away_pitcher_norm', 'season'],
        how='left'
    )

    feature_cols = [
        'date', 'season', 'month', 'is_day',
        'home_team', 'away_team', 'home_win',
        'home_rolling_win_rate', 'home_rolling_runs_scored',
        'home_rolling_runs_allowed', 'home_rolling_run_diff',
        'home_rolling_home_win_rate', 'away_rolling_win_rate',
        'away_rolling_runs_scored', 'away_rolling_runs_allowed',
        'away_rolling_run_diff', 'away_rolling_away_win_rate',
        'home_starter_era', 'home_starter_whip', 'home_starter_so9',
        'away_starter_era', 'away_starter_whip', 'away_starter_so9',
    ]

    games = games[[c for c in feature_cols if c in games.columns]]
    games = games.dropna(subset=[
        'home_rolling_win_rate', 'away_rolling_win_rate',
        'home_rolling_home_win_rate', 'away_rolling_away_win_rate',
    ])

    return games.reset_index(drop=True)


def encode_teams(df):
    encoders = {}
    for col in ['home_team', 'away_team']:
        le = LabelEncoder()
        df[f'{col}_enc'] = le.fit_transform(df[col])
        encoders[col] = le
    return df, encoders


def time_split(df):
    train = df[df['season'].astype(int) <= 2024].copy()
    test = df[df['season'].astype(int) >= 2025].copy()
    return train, test


def main():
    print("Loading raw data...")
    raw_path = INPUT_RAW / "game_results.csv"
    schedule_path = INPUT_RAW / "game_schedule.csv"
    pitching_path = INPUT_RAW / "pitching_stats.csv"

    df = load_and_clean(raw_path)
    print(f"  Clean rows: {len(df)}")

    df = add_rolling_features(df)

    schedule = load_schedule(schedule_path)
    pitching = load_pitching(pitching_path)

    games = build_game_features(df, schedule, pitching)
    print(f"  Game rows: {len(games)}")

    games, encoders = encode_teams(games)
    train, test = time_split(games)
    print(f"  Train: {len(train)}, Test: {len(test)}")

    # Save train and test feature matrices
    # SageMaker XGBoost built-in expects CSV with target as first column
    # and no header
    train_out = OUTPUT_PATH / "train"
    test_out = OUTPUT_PATH / "test"
    train_out.mkdir(parents=True, exist_ok=True)
    test_out.mkdir(parents=True, exist_ok=True)

    train_features = train[FEATURE_COLS]
    test_features = test[FEATURE_COLS]
    train_target = train[TARGET_COL]
    test_target = test[TARGET_COL]

    # Fill NaN with median for SageMaker XGBoost
    medians = train_features.median()
    train_features = train_features.fillna(medians)
    test_features = test_features.fillna(medians)

    # SageMaker XGBoost built-in: target first, no header
    train_csv = pd.concat([train_target.reset_index(drop=True),
                           train_features.reset_index(drop=True)], axis=1)
    test_csv = pd.concat([test_target.reset_index(drop=True),
                          test_features.reset_index(drop=True)], axis=1)

    train_csv.to_csv(train_out / "train.csv", index=False, header=False)
    test_csv.to_csv(test_out / "test.csv", index=False, header=False)

    # Save medians for use in evaluation and inference
    medians_dict = medians.to_dict()
    with open(OUTPUT_PATH / "medians.json", 'w') as f:
        json.dump(medians_dict, f)

    print(f"  Saved train: {len(train_csv)} rows")
    print(f"  Saved test: {len(test_csv)} rows")
    print("Feature engineering complete.")


if __name__ == "__main__":
    main()