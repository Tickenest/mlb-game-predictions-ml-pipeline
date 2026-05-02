import time
import pandas as pd
from pybaseball import schedule_and_record

TEAMS = [
    'ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET',
    'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'OAK',
    'PHI', 'PIT', 'SDP', 'SFG', 'SEA', 'STL', 'TBR', 'TEX', 'TOR', 'WSN'
]

SEASONS = [2021, 2022, 2023, 2024, 2025]

all_records = []

for season in SEASONS:
    print(f"\n=== Season {season} ===")
    for team in TEAMS:
        try:
            df = schedule_and_record(season, team)
            df['season'] = season
            all_records.append(df)
            print(f"  {team}: {len(df)} games")
            time.sleep(4)  # be polite to Baseball Reference
        except Exception as e:
            print(f"  {team}: ERROR — {e}")

combined = pd.concat(all_records, ignore_index=True)
print(f"\nTotal rows: {len(combined)}")
print(f"Columns: {list(combined.columns)}")

combined.to_csv("data/raw_game_results.csv", index=False)
print("\nSaved to data/raw_game_results.csv")