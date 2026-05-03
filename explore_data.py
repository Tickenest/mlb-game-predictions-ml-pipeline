import pandas as pd

df = pd.read_csv("data/game_schedule.csv")
print(f"Total games: {len(df)}")
print(f"Home probable pitcher present: {df['home_probable'].notna().sum()} ({df['home_probable'].notna().mean():.1%})")
print(f"Away probable pitcher present: {df['away_probable'].notna().sum()} ({df['away_probable'].notna().mean():.1%})")
print(f"\nSample rows missing probable pitchers:")
print(df[df['home_probable'].isna()][['date', 'home_team', 'away_team', 'season']].head(10))