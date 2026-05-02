import pandas as pd
import numpy as np
from pathlib import Path

RAW_DATA_PATH = Path("data/raw_game_results.csv")
PROCESSED_DATA_PATH = Path("data/processed/features.csv")
ROLLING_WINDOW = 15  # games to look back for rolling stats


def load_and_clean(path: Path) -> pd.DataFrame:
    """Load raw data and clean it up."""
    df = pd.read_csv(path)

    # Drop rows with no result (future games, postponements)
    df = df[df['W/L'].isin(['W', 'L', 'W-wo', 'L-wo'])].copy()

    # Normalize W/L to binary
    df['win'] = df['W/L'].isin(['W', 'W-wo']).astype(int)

    # Normalize home/away
    df['is_home'] = (df['Home_Away'] == 'Home').astype(int)

    # Day/night
    df['is_day'] = (df['D/N'] == 'D').astype(int)

    # Parse runs as numeric
    df['R'] = pd.to_numeric(df['R'], errors='coerce')
    df['RA'] = pd.to_numeric(df['RA'], errors='coerce')
    df['run_diff'] = df['R'] - df['RA']

    # Parse date — format is like "Thursday, Mar 30"
    # Add season year to make it parseable
    df['date_clean'] = df['Date'].str.replace(r'\s*\(\d\)$', '', regex=True)
    df['date_str'] = df['date_clean'].str.extract(r'(\w+ \d+)$')[0] + ' ' + df['season'].astype(str)
    df['date'] = pd.to_datetime(df['date_str'], format='mixed', errors='coerce')
    df['month'] = df['date'].dt.month

    df['game_num'] = df['Date'].str.extract(r'\((\d)\)$')[0].fillna('1')

    # Drop columns we don't need
    drop_cols = ['W/L', 'Home_Away', 'Inn', 'W-L', 'Rank', 'GB', 'Win',
                 'Loss', 'Save', 'Time', 'D/N', 'Attendance', 'cLI',
                 'Streak', 'Orig. Scheduled', 'date_str', 'Date']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    # Sort by team and date for rolling calculations
    df = df.sort_values(['Tm', 'date']).reset_index(drop=True)

    return df


def add_rolling_features(df: pd.DataFrame, window: int = ROLLING_WINDOW) -> pd.DataFrame:
    """Add rolling statistics per team."""
    df = df.copy()

    # Calculate rolling stats per team using shift(1) to avoid data leakage
    # shift(1) means we use stats from games BEFORE the current one
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

    # Home win rate
    home_wins = df[df['is_home'] == 1].copy()
    home_win_rate = (
        home_wins.groupby('Tm')['win']
        .transform(lambda x: x.shift(1).rolling(window, min_periods=3).mean())
    )
    df.loc[df['is_home'] == 1, 'rolling_home_win_rate'] = home_win_rate

    # Away win rate
    away_games = df[df['is_home'] == 0].copy()
    away_win_rate = (
        away_games.groupby('Tm')['win']
        .transform(lambda x: x.shift(1).rolling(window, min_periods=3).mean())
    )
    df.loc[df['is_home'] == 0, 'rolling_away_win_rate'] = away_win_rate

    return df


def build_game_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build one row per game (not per team-game).
    Each row represents a game from the HOME team's perspective.
    Target: home_win = 1 if home team won, 0 if away team won.
    """
    # Separate home and away records
    home = df[df['is_home'] == 1].copy()
    away = df[df['is_home'] == 0].copy()

    # Rename columns for home team
    home = home.rename(columns={
        'Tm': 'home_team',
        'Opp': 'away_team',
        'win': 'home_win',
        'rolling_win_rate': 'home_rolling_win_rate',
        'rolling_runs_scored': 'home_rolling_runs_scored',
        'rolling_runs_allowed': 'home_rolling_runs_allowed',
        'rolling_run_diff': 'home_rolling_run_diff',
        'rolling_home_win_rate': 'home_rolling_home_win_rate',
    })

    # Rename columns for away team
    away = away.rename(columns={
        'Tm': 'away_team_check',
        'rolling_win_rate': 'away_rolling_win_rate',
        'rolling_runs_scored': 'away_rolling_runs_scored',
        'rolling_runs_allowed': 'away_rolling_runs_allowed',
        'rolling_run_diff': 'away_rolling_run_diff',
        'rolling_away_win_rate': 'away_rolling_away_win_rate',
    })

    # Select only what we need from away
    away_cols = [
        'away_team_check', 'date', 'season',
        'away_rolling_win_rate', 'away_rolling_runs_scored',
        'away_rolling_runs_allowed', 'away_rolling_run_diff',
        'away_rolling_away_win_rate',
    ]
    away = away[away_cols]

    # Merge home and away on date and matching teams
    games = home.merge(
        away,
        left_on=['away_team', 'date', 'season'],
        right_on=['away_team_check', 'date', 'season'],
        how='inner'
    )

    # Drop redundant column
    games = games.drop(columns=['away_team_check'])

    # Final feature columns
    feature_cols = [
        'date', 'season', 'month', 'is_day',
        'home_team', 'away_team',
        'home_win',
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
    ]

    games = games[[c for c in feature_cols if c in games.columns]]
    games = games.dropna(subset=[
        'home_rolling_win_rate', 'away_rolling_win_rate'
    ])

    return games.reset_index(drop=True)


def main():
    print("Loading and cleaning raw data...")
    df = load_and_clean(RAW_DATA_PATH)
    print(f"  Clean rows: {len(df)}")

    print("Adding rolling features...")
    df = add_rolling_features(df)
    print(f"  Rows after rolling: {len(df)}")

    print("Building game-level features...")
    games = build_game_features(df)
    print(f"  Game rows: {len(games)}")
    print(f"  Columns: {list(games.columns)}")
    print(f"\nHome win rate: {games['home_win'].mean():.3f}")
    print(f"\nNull counts:")
    print(games.isnull().sum()[games.isnull().sum() > 0])
    print(f"\nSample row:")
    print(games.iloc[100])

    games = games.dropna(subset=[
        'home_rolling_win_rate',
        'away_rolling_win_rate',
        'home_rolling_home_win_rate',
        'away_rolling_away_win_rate',
    ])

    PROCESSED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    games.to_csv(PROCESSED_DATA_PATH, index=False)
    print(f"\nSaved to {PROCESSED_DATA_PATH}")


if __name__ == "__main__":
    main()