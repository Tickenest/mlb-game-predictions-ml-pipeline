import pandas as pd
import re

df = pd.read_csv("data/raw_game_results.csv")
df = df[df['W/L'].isin(['W', 'L', 'W-wo', 'L-wo'])].copy()
df['season'] = df['season'].astype(str)

# Try the extraction
df['date_str'] = df['Date'].str.extract(r'(\w+ \d+)$')[0] + ' ' + df['season']
df['date'] = pd.to_datetime(df['date_str'], format='mixed', errors='coerce')

# Show rows where date parsing failed
failed = df[df['date'].isna()]
print(f"Failed date parses: {len(failed)}")
print("\nSample failed rows:")
print(failed[['Date', 'season', 'date_str']].head(20))