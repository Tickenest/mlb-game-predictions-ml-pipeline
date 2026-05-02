from pybaseball import schedule_and_record
import pandas as pd

# All 30 MLB team abbreviations
TEAMS = [
    'ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET',
    'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'OAK',
    'PHI', 'PIT', 'SDP', 'SFG', 'SEA', 'STL', 'TBR', 'TEX', 'TOR', 'WSN'
]

print(f"Total teams: {len(TEAMS)}")
print(f"Seasons: 2021-2025")
print(f"Estimated API calls: {len(TEAMS) * 5} (one per team per season)")
print(f"Estimated games in dataset: ~{len(TEAMS) * 162 * 5 // 2} unique games")

# Test one more team and season to verify consistency
results = schedule_and_record(2021, 'LAD')
print(f"\n2021 LAD shape: {results.shape}")
print(f"W/L values: {results['W/L'].unique()}")
print(f"Home_Away values: {results['Home_Away'].unique()}")