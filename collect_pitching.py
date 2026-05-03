import time
import pandas as pd
from pybaseball import pitching_stats_bref

SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
all_pitching = []

for season in SEASONS:
    print(f"Fetching {season} pitching stats...")
    try:
        df = pitching_stats_bref(season)
        df['season'] = season
        all_pitching.append(df)
        print(f"  {len(df)} pitchers")
        time.sleep(4)
    except Exception as e:
        print(f"  ERROR: {e}")

combined = pd.concat(all_pitching, ignore_index=True)
print(f"\nTotal rows: {len(combined)}")

# Keep all pitchers — separate starters and relievers in feature engineering
keep_cols = ['Name', 'Tm', 'GS', 'G', 'IP', 'ERA', 'WHIP', 'SO9', 'SO/W', 'season']
combined = combined[[c for c in keep_cols if c in combined.columns]]

print(f"Starters (GS > 0): {len(combined[combined['GS'] > 0])}")
print(f"Relievers (GS == 0): {len(combined[combined['GS'] == 0])}")

combined.to_csv("data/pitching_stats.csv", index=False)
print("Saved to data/pitching_stats.csv")