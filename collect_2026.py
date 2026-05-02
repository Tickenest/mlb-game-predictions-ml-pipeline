import time
import pandas as pd
from pybaseball import schedule_and_record

TEAMS = [
    'ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET',
    'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'ATH',
    'PHI', 'PIT', 'SDP', 'SFG', 'SEA', 'STL', 'TBR', 'TEX', 'TOR', 'WSN'
]

all_records = []

print("=== Season 2026 ===")
for team in TEAMS:
    try:
        df = schedule_and_record(2026, team)
        df['season'] = 2026
        all_records.append(df)
        print(f"  {team}: {len(df)} games")
        time.sleep(4)
    except Exception as e:
        print(f"  {team}: ERROR — {e}")

new_data = pd.concat(all_records, ignore_index=True)
print(f"\n2026 rows collected: {len(new_data)}")

# Load existing data and append
existing = pd.read_csv("data/raw_game_results.csv")
print(f"Existing rows: {len(existing)}")

combined = pd.concat([existing, new_data], ignore_index=True)
print(f"Combined rows: {len(combined)}")

combined.to_csv("data/raw_game_results.csv", index=False)
print("Saved to data/raw_game_results.csv")