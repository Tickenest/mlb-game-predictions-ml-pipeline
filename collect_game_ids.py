import requests
import pandas as pd
import time
from datetime import date

def get_schedule_range(start_date: str, end_date: str) -> list:
    """Get all games in a date range."""
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "startDate": start_date,
        "endDate": end_date,
        "sportId": 1,
        "hydrate": "probablePitcher",
        "gameType": "R",  # regular season only
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    games = []
    for date_entry in data.get('dates', []):
        for game in date_entry.get('games', []):
            games.append({
                'game_pk': game['gamePk'],
                'date': date_entry['date'],
                'home_team': game['teams']['home']['team']['name'],
                'away_team': game['teams']['away']['team']['name'],
                'home_team_abbrev': game['teams']['home']['team'].get('abbreviation', ''),
                'away_team_abbrev': game['teams']['away']['team'].get('abbreviation', ''),
                'home_probable': game['teams']['home'].get('probablePitcher', {}).get('fullName', None),
                'away_probable': game['teams']['away'].get('probablePitcher', {}).get('fullName', None),
                'status': game['status']['detailedState'],
                'season': int(date_entry['date'][:4]),
            })
    return games

# Fetch by season to avoid huge single requests
seasons = [
    ("2021-04-01", "2021-11-05"),
    ("2022-04-07", "2022-11-05"),
    ("2023-03-30", "2023-11-05"),
    ("2024-03-20", "2024-11-02"),
    ("2025-03-18", "2025-11-05"),
    ("2026-03-26", "2026-11-05"),
]

all_games = []
for start, end in seasons:
    print(f"Fetching {start[:4]} schedule...")
    games = get_schedule_range(start, end)
    # Only keep final games
    final = [g for g in games if g['status'] == 'Final']
    all_games.extend(final)
    print(f"  {len(final)} completed games")
    time.sleep(1)

df = pd.DataFrame(all_games)
print(f"\nTotal games: {len(df)}")
print(df.head())
df.to_csv("data/game_schedule.csv", index=False)
print("Saved to data/game_schedule.csv")