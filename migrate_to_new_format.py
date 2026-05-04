import requests
import pandas as pd
import time
from pathlib import Path

SCHEDULE_PATH = Path("data/game_schedule.csv")
OUTPUT_PATH = Path("data/game_results_new.csv")

NAME_TO_ABBREV = {
    'Arizona Diamondbacks': 'ARI', 'Atlanta Braves': 'ATL',
    'Baltimore Orioles': 'BAL', 'Boston Red Sox': 'BOS',
    'Chicago Cubs': 'CHC', 'Chicago White Sox': 'CHW',
    'Cincinnati Reds': 'CIN', 'Cleveland Guardians': 'CLE',
    'Cleveland Indians': 'CLE', 'Colorado Rockies': 'COL',
    'Detroit Tigers': 'DET', 'Houston Astros': 'HOU',
    'Kansas City Royals': 'KCR', 'Los Angeles Angels': 'LAA',
    'Los Angeles Dodgers': 'LAD', 'Miami Marlins': 'MIA',
    'Milwaukee Brewers': 'MIL', 'Minnesota Twins': 'MIN',
    'New York Mets': 'NYM', 'New York Yankees': 'NYY',
    'Athletics': 'ATH', 'Oakland Athletics': 'ATH',
    'Philadelphia Phillies': 'PHI', 'Pittsburgh Pirates': 'PIT',
    'San Diego Padres': 'SDP', 'San Francisco Giants': 'SFG',
    'Seattle Mariners': 'SEA', 'St. Louis Cardinals': 'STL',
    'Tampa Bay Rays': 'TBR', 'Texas Rangers': 'TEX',
    'Toronto Blue Jays': 'TOR', 'Washington Nationals': 'WSN',
}


def get_game_result(game_pk: int, retries: int = 3) -> dict | None:
    """Fetch final score for a completed game from MLB Stats API."""
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/linescore"
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 429:
                print(f"  RATE LIMITED on game {game_pk} — waiting 30 seconds...")
                time.sleep(30)
                continue
            response.raise_for_status()
            data = response.json()
            home_score = data.get('teams', {}).get('home', {}).get('runs')
            away_score = data.get('teams', {}).get('away', {}).get('runs')
            if home_score is None or away_score is None:
                return None
            return {
                'home_score': int(home_score),
                'away_score': int(away_score),
                'home_win': 1 if home_score > away_score else 0,
            }
        except requests.exceptions.RequestException as e:
            print(f"  ERROR on game {game_pk} attempt {attempt + 1}: {e}")
            if attempt < retries - 1:
                time.sleep(5)
    return None


def main():
    print("Loading schedule...")
    schedule = pd.read_csv(SCHEDULE_PATH)
    schedule = schedule[schedule['status'] == 'Final'].copy()
    print(f"  Total completed games: {len(schedule)}")

    # Check if we have a partial output to resume from
    if OUTPUT_PATH.exists():
        existing = pd.read_csv(OUTPUT_PATH)
        done_pks = set(existing['game_pk'].astype(str))
        print(f"  Resuming from existing output — {len(done_pks)} games already done")
    else:
        existing = pd.DataFrame()
        done_pks = set()

    remaining = schedule[~schedule['game_pk'].astype(str).isin(done_pks)]
    print(f"  Games remaining: {len(remaining)}")

    results = []
    total = len(remaining)

    for i, (_, row) in enumerate(remaining.iterrows()):
        game_pk = int(row['game_pk'])

        if (i + 1) % 100 == 0:
            print(f"  Progress: {i + 1}/{total} ({(i+1)/total*100:.1f}%)")
            # Save checkpoint every 100 games
            checkpoint = pd.concat([existing, pd.DataFrame(results)], ignore_index=True)
            checkpoint.to_csv(OUTPUT_PATH, index=False)
            print(f"  Checkpoint saved ({len(checkpoint)} rows)")

        result = get_game_result(game_pk)
        if result is None:
            print(f"  Skipping game {game_pk} — no score data")
            continue

        results.append({
            'game_pk': game_pk,
            'date': row['date'],
            'season': int(row['season']),
            'home_team': NAME_TO_ABBREV.get(row['home_team'], row.get('home_team_abbrev', 'UNK')),
            'away_team': NAME_TO_ABBREV.get(row['away_team'], row.get('away_team_abbrev', 'UNK')),
            'home_team_full': row['home_team'],
            'away_team_full': row['away_team'],
            'home_score': result['home_score'],
            'away_score': result['away_score'],
            'home_win': result['home_win'],
            'home_pitcher': row.get('home_probable'),
            'away_pitcher': row.get('away_probable'),
            'status': 'Final',
        })

        # Small delay to be polite to the API
        time.sleep(0.1)

    # Final save
    final = pd.concat([existing, pd.DataFrame(results)], ignore_index=True)
    final = final.sort_values(['season', 'date']).reset_index(drop=True)
    final.to_csv(OUTPUT_PATH, index=False)
    print(f"\nDone! Total rows: {len(final)}")
    print(f"Saved to {OUTPUT_PATH}")
    print(f"\nSample row:")
    print(final.iloc[0].to_dict())


if __name__ == "__main__":
    main()