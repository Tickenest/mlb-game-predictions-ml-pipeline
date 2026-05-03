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
    df['home_pitcher_norm'] = df['home_probable'].apply(normalize_name)
    df['away_pitcher_norm'] = df['away_probable'].apply(normalize_name)
    return df


def load_pitching(path: Path) -> pd.DataFrame:
    """Load pitcher seasonal stats."""
    df = pd.read_csv(path)
    df['pitcher_norm'] = df['Name'].apply(normalize_name)
    for col in ['ERA', 'WHIP', 'SO9']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['ERA'] = df['ERA'].clip(upper=15)
    df['IP'] = pd.to_numeric(df['IP'], errors='coerce')
    df['GS'] = pd.to_numeric(df['GS'], errors='coerce').fillna(0)

    # For traded players, keep only their primary team (first listed)
    # and also keep the combined row for season totals
    # Split on comma and take first team for team-level aggregations
    df['team_primary'] = df['Tm'].str.split(',').str[0].str.strip()

    return df


def compute_bullpen_era(pitching: pd.DataFrame) -> pd.DataFrame:
    """
    Compute weighted bullpen ERA per team per season.
    Bullpen = pitchers with GS == 0.
    """
    # Map Baseball Reference city names to full team names
    br_to_full = {
        'Arizona': 'Arizona Diamondbacks',
        'Atlanta': 'Atlanta Braves',
        'Baltimore': 'Baltimore Orioles',
        'Boston': 'Boston Red Sox',
        'Chicago': None,  # ambiguous — handled below
        'Cincinnati': 'Cincinnati Reds',
        'Cleveland': 'Cleveland Guardians',
        'Colorado': 'Colorado Rockies',
        'Detroit': 'Detroit Tigers',
        'Houston': 'Houston Astros',
        'Kansas City': 'Kansas City Royals',
        'Los Angeles': None,  # ambiguous — handled below
        'Miami': 'Miami Marlins',
        'Milwaukee': 'Milwaukee Brewers',
        'Minnesota': 'Minnesota Twins',
        'New York': None,  # ambiguous — handled below
        'Oakland': 'Oakland Athletics',
        'Athletics': 'Athletics',
        'Philadelphia': 'Philadelphia Phillies',
        'Pittsburgh': 'Pittsburgh Pirates',
        'San Diego': 'San Diego Padres',
        'San Francisco': 'San Francisco Giants',
        'Seattle': 'Seattle Mariners',
        'St. Louis': 'St. Louis Cardinals',
        'Tampa Bay': 'Tampa Bay Rays',
        'Texas': 'Texas Rangers',
        'Toronto': 'Toronto Blue Jays',
        'Washington': 'Washington Nationals',
    }

    bullpen = pitching[pitching['GS'] == 0].copy()

    # For traded players keep only rows where team is a single team
    # (not combined stats rows like "Arizona,Baltimore")
    bullpen = bullpen[~bullpen['team_primary'].str.contains(',', na=False)]

    # For ambiguous cities, use the Name column to resolve
    # Baseball Reference uses the same city for both teams
    # We'll handle Chicago, Los Angeles, New York by keeping both
    # and letting the weighted average sort it out — but we need
    # to flag them. For now map them to NaN and drop.
    bullpen['team_full'] = bullpen['team_primary'].map(br_to_full)

    # Drop ambiguous rows (Chicago, LA, NY) and unmapped
    bullpen = bullpen[bullpen['team_full'].notna()]

    print(f"  Bullpen rows after cleaning: {len(bullpen)}")
    print(f"  Unique teams: {sorted(bullpen['team_full'].unique())}")

    bullpen['ER'] = bullpen['ERA'] * bullpen['IP'] / 9

    team_bullpen = (
        bullpen.groupby(['team_full', 'season'])
        .agg(
            total_er=('ER', 'sum'),
            total_ip=('IP', 'sum')
        )
        .reset_index()
    )

    team_bullpen['bullpen_era'] = (
        team_bullpen['total_er'] / team_bullpen['total_ip'] * 9
    ).clip(upper=15)

    return team_bullpen[['team_full', 'season', 'bullpen_era']]


def compute_starter_days_rest(schedule: pd.DataFrame) -> pd.DataFrame:
    """
    Compute days of rest for each starting pitcher on each game date.
    """
    home_starts = schedule[schedule['home_probable'].notna()][
        ['date', 'home_probable']
    ].rename(columns={'home_probable': 'pitcher'})

    away_starts = schedule[schedule['away_probable'].notna()][
        ['date', 'away_probable']
    ].rename(columns={'away_probable': 'pitcher'})

    all_starts = pd.concat([home_starts, away_starts], ignore_index=True)
    all_starts = all_starts.drop_duplicates(subset=['pitcher', 'date'])
    all_starts = all_starts.sort_values(['pitcher', 'date'])

    all_starts['prev_start'] = all_starts.groupby('pitcher')['date'].shift(1)
    all_starts['days_rest'] = (
        all_starts['date'] - all_starts['prev_start']
    ).dt.days.clip(upper=30)

    # Normalize pitcher name for joining
    all_starts['pitcher_norm'] = all_starts['pitcher'].apply(normalize_name)

    return all_starts[['pitcher_norm', 'date', 'days_rest']]


def build_game_features(df: pd.DataFrame, schedule: pd.DataFrame,
                         pitching: pd.DataFrame) -> pd.DataFrame:
    """Build one row per game with team and pitcher features."""

    print("  Pitching columns:", list(pitching.columns))
    print("  Schedule columns:", list(schedule.columns))

    # Separate home and away
    home = df[df['is_home'] == 1].copy()
    away = df[df['is_home'] == 0].copy()

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

    # Team abbreviation to full name mapping
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

    # Merge with schedule to get pitcher names
    schedule_slim = schedule[[
        'date', 'home_team', 'away_team',
        'home_pitcher_norm', 'away_pitcher_norm', 'season'
    ]].copy()

    games = games.merge(
        schedule_slim,
        left_on=['date', 'home_team_full', 'season'],
        right_on=['date', 'home_team', 'season'],
        how='left',
        suffixes=('', '_sched')
    )

    # Drop redundant schedule columns
    games = games.drop(
        columns=[c for c in games.columns if c.endswith('_sched')],
        errors='ignore'
    )

    print("  Pitcher columns after schedule merge:",
          [c for c in games.columns if 'pitcher' in c.lower()])

    # Join home pitcher stats (starters only)
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

    # Join bullpen ERA
    bullpen_era = compute_bullpen_era(pitching)
    print(f"  Bullpen ERA rows: {len(bullpen_era)}")
    print(f"  Sample bullpen ERA:\n{bullpen_era.head()}")

    # We need to map team abbreviations to match pitching stats team names
    # Pitching stats use full team names from Baseball Reference
    # Build reverse map: full name -> abbrev
    full_to_abbrev = {v: k for k, v in abbrev_map.items()}

    # Check what team names look like in pitching stats
    print("  Sample team names in pitching:", pitching['Tm'].unique()[:10])

    # Join home bullpen ERA
    games = games.merge(
        bullpen_era.rename(columns={
            'team_full': 'home_team_full',
            'bullpen_era': 'home_bullpen_era'
        }),
        on=['home_team_full', 'season'],
        how='left'
    )

    # Join away bullpen ERA
    games = games.merge(
        bullpen_era.rename(columns={
            'team_full': 'away_team_full',
            'bullpen_era': 'away_bullpen_era'
        }),
        on=['away_team_full', 'season'],
        how='left'
    )

    # Join starter days of rest
    days_rest = compute_starter_days_rest(schedule)
    print(f"  Days rest rows: {len(days_rest)}")

    # Home starter days rest
    games = games.merge(
        days_rest.rename(columns={
            'pitcher_norm': 'home_pitcher_norm',
            'days_rest': 'home_starter_days_rest'
        }),
        on=['home_pitcher_norm', 'date'],
        how='left'
    )

    # Away starter days rest
    games = games.merge(
        days_rest.rename(columns={
            'pitcher_norm': 'away_pitcher_norm',
            'days_rest': 'away_starter_days_rest'
        }),
        on=['away_pitcher_norm', 'date'],
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
        'home_bullpen_era',
        'away_bullpen_era',
        'home_starter_days_rest',
        'away_starter_days_rest',
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
    print(f"  Home ERA: {games['home_starter_era'].notna().sum()} ({games['home_starter_era'].notna().mean():.1%})")
    print(f"  Away ERA: {games['away_starter_era'].notna().sum()} ({games['away_starter_era'].notna().mean():.1%})")
    print(f"  Home bullpen ERA: {games['home_bullpen_era'].notna().sum()} ({games['home_bullpen_era'].notna().mean():.1%})")
    print(f"  Away bullpen ERA: {games['away_bullpen_era'].notna().sum()} ({games['away_bullpen_era'].notna().mean():.1%})")
    print(f"  Home days rest: {games['home_starter_days_rest'].notna().sum()} ({games['home_starter_days_rest'].notna().mean():.1%})")
    print(f"  Away days rest: {games['away_starter_days_rest'].notna().sum()} ({games['away_starter_days_rest'].notna().mean():.1%})")

    print(f"\nNull counts:")
    print(games.isnull().sum()[games.isnull().sum() > 0])

    PROCESSED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    games.to_csv(PROCESSED_DATA_PATH, index=False)
    print(f"\nSaved to {PROCESSED_DATA_PATH}")


if __name__ == "__main__":
    main()