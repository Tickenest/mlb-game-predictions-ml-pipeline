import pandas as pd
import numpy as np
import unicodedata
from pathlib import Path

RAW_DATA_PATH = Path("data/raw_game_results.csv")
SCHEDULE_PATH = Path("data/game_schedule.csv")
PITCHING_PATH = Path("data/pitching_stats.csv")
PROCESSED_DATA_PATH = Path("data/processed/features_v2.csv")
ROLLING_WINDOW = 15


def normalize_name(name: str) -> str:
    """Normalize pitcher name for joining — strip accents, lowercase."""
    if pd.isna(name):
        return name
    nfkd = unicodedata.normalize('NFKD', str(name))
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_name.lower().strip()


def load_and_clean(path: Path) -> pd.DataFrame:
    """Load raw game results and clean."""
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
    df['date'] = pd.to_datetime(df['date_str'], format='mixed', errors='coerce')
    df['month'] = df['date'].dt.month
    df['game_num'] = df['Date'].str.extract(r'\((\d)\)$')[0].fillna('1')

    drop_cols = ['W/L', 'Home_Away', 'Inn', 'W-L', 'Rank', 'GB', 'Win',
                 'Loss', 'Save', 'Time', 'D/N', 'Attendance', 'cLI',
                 'Streak', 'Orig. Scheduled', 'date_str', 'Date', 'date_clean']
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])
    df = df.sort_values(['Tm', 'date']).reset_index(drop=True)
    return df


def add_rolling_features(df: pd.DataFrame, window: int = ROLLING_WINDOW) -> pd.DataFrame:
    """Add rolling team statistics."""
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


def load_schedule(path: Path) -> pd.DataFrame:
    """Load MLB API schedule with probable pitchers."""
    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'])

    # Normalize pitcher names
    df['home_pitcher_norm'] = df['home_probable'].apply(normalize_name)
    df['away_pitcher_norm'] = df['away_probable'].apply(normalize_name)

    return df


def load_pitching(path: Path) -> pd.DataFrame:
    """Load pitcher seasonal stats."""
    df = pd.read_csv(path)

    # Normalize names
    df['pitcher_norm'] = df['Name'].apply(normalize_name)

    # Keep only relevant columns
    keep = ['pitcher_norm', 'season', 'ERA', 'WHIP', 'SO9', 'GS', 'IP']
    df = df[[c for c in keep if c in df.columns]]

    # Convert to numeric
    for col in ['ERA', 'WHIP', 'SO9']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Cap ERA at 15 to handle outliers with tiny IP
    df['ERA'] = df['ERA'].clip(upper=15)

    return df


def build_game_features(df: pd.DataFrame, schedule: pd.DataFrame,
                         pitching: pd.DataFrame) -> pd.DataFrame:
    """Build one row per game with team and pitcher features."""

    # Separate home and away
    home = df[df['is_home'] == 1].copy()
    away = df[df['is_home'] == 0].copy()

    # Rename home columns
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

    # Rename away columns
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

    # Merge home and away
    games = home.merge(
        away,
        left_on=['away_team', 'date', 'season', 'game_num'],
        right_on=['away_team_check', 'date', 'season', 'game_num'],
        how='inner'
    )
    games = games.drop(columns=['away_team_check'])

    # Merge with schedule to get pitcher names
    # Match on date — use abbreviation mapping
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
        'CLE': 'Cleveland Indians',
    }

    games['home_team_full'] = games['home_team'].map(abbrev_map)
    games['away_team_full'] = games['away_team'].map(abbrev_map)

    # Merge with schedule on date and home team name
    schedule_slim = schedule[[
        'date', 'home_team', 'away_team',
        'home_pitcher_norm', 'away_pitcher_norm', 'season'
    ]].copy()

    # Try matching on date + season
    games = games.merge(
        schedule_slim,
        left_on=['date', 'home_team_full', 'season'],
        right_on=['date', 'home_team', 'season'],
        how='left'
    )
    games = games.drop(columns=['home_team_y', 'away_team_y'],
                       errors='ignore')
    games = games.rename(columns={
        'home_team_x': 'home_team',
        'away_team_x': 'away_team',
    })

    # Join home pitcher stats
    games = games.merge(
        pitching.rename(columns={
            'pitcher_norm': 'home_pitcher_norm',
            'ERA': 'home_starter_era',
            'WHIP': 'home_starter_whip',
            'SO9': 'home_starter_so9',
        }),
        on=['home_pitcher_norm', 'season'],
        how='left'
    )

    # Join away pitcher stats
    games = games.merge(
        pitching.rename(columns={
            'pitcher_norm': 'away_pitcher_norm',
            'ERA': 'away_starter_era',
            'WHIP': 'away_starter_whip',
            'SO9': 'away_starter_so9',
        }),
        on=['away_pitcher_norm', 'season'],
        how='left'
    )

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
        'home_starter_era',
        'home_starter_whip',
        'home_starter_so9',
        'away_starter_era',
        'away_starter_whip',
        'away_starter_so9',
    ]

    games = games[[c for c in feature_cols if c in games.columns]]
    games = games.dropna(subset=[
        'home_rolling_win_rate',
        'away_rolling_win_rate',
        'home_rolling_home_win_rate',
        'away_rolling_away_win_rate',
    ])

    return games.reset_index(drop=True)


def main():
    print("Loading and cleaning raw data...")
    df = load_and_clean(RAW_DATA_PATH)
    print(f"  Clean rows: {len(df)}")

    print("Adding rolling features...")
    df = add_rolling_features(df)

    print("Loading schedule...")
    schedule = load_schedule(SCHEDULE_PATH)
    print(f"  Schedule rows: {len(schedule)}")

    print("Loading pitching stats...")
    pitching = load_pitching(PITCHING_PATH)
    print(f"  Pitcher rows: {len(pitching)}")

    print("Building game features...")
    games = build_game_features(df, schedule, pitching)
    print(f"  Game rows: {len(games)}")

    print(f"\nHome win rate: {games['home_win'].mean():.3f}")
    print(f"\nPitcher stat coverage:")
    print(f"  Home ERA present: {games['home_starter_era'].notna().sum()} ({games['home_starter_era'].notna().mean():.1%})")
    print(f"  Away ERA present: {games['away_starter_era'].notna().sum()} ({games['away_starter_era'].notna().mean():.1%})")

    print(f"\nNull counts:")
    print(games.isnull().sum()[games.isnull().sum() > 0])

    PROCESSED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    games.to_csv(PROCESSED_DATA_PATH, index=False)
    print(f"\nSaved to {PROCESSED_DATA_PATH}")


if __name__ == "__main__":
    main()