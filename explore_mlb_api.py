import requests
import json

def get_schedule(date: str) -> dict:
    """Get schedule and probable pitchers for a given date."""
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "date": date,
        "sportId": 1,
        "hydrate": "probablePitcher,linescore"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def get_box_score(game_pk: int) -> dict:
    """Get box score for a specific game including starting pitchers."""
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

# Test with a past date
date = "2023-04-01"
print(f"=== Schedule for {date} ===")
schedule = get_schedule(date)

games = schedule.get('dates', [{}])[0].get('games', [])
print(f"Games found: {len(games)}")

for game in games[:3]:
    game_pk = game['gamePk']
    home = game['teams']['home']['team']['name']
    away = game['teams']['away']['team']['name']
    status = game['status']['detailedState']

    home_pitcher = game['teams']['home'].get('probablePitcher', {}).get('fullName', 'Unknown')
    away_pitcher = game['teams']['away'].get('probablePitcher', {}).get('fullName', 'Unknown')

    print(f"\nGame {game_pk}: {away} @ {home}")
    print(f"  Status: {status}")
    print(f"  Home starter: {home_pitcher}")
    print(f"  Away starter: {away_pitcher}")

    # Get actual box score to confirm starters
    print(f"  Fetching box score...")
    box = get_box_score(game_pk)

    home_pitchers = box.get('teams', {}).get('home', {}).get('pitchers', [])
    away_pitchers = box.get('teams', {}).get('away', {}).get('pitchers', [])

    home_pitcher_info = box.get('teams', {}).get('home', {}).get('players', {})
    away_pitcher_info = box.get('teams', {}).get('away', {}).get('players', {})

    if home_pitchers:
        starter_id = f"ID{home_pitchers[0]}"
        starter = home_pitcher_info.get(starter_id, {}).get('person', {}).get('fullName', 'Unknown')
        print(f"  Actual home starter: {starter}")

    if away_pitchers:
        starter_id = f"ID{away_pitchers[0]}"
        starter = away_pitcher_info.get(starter_id, {}).get('person', {}).get('fullName', 'Unknown')
        print(f"  Actual away starter: {starter}")

# Also test today's games for probable pitchers
import datetime
today = datetime.date.today().isoformat()
print(f"\n=== Today's Games ({today}) ===")
schedule_today = get_schedule(today)
games_today = schedule_today.get('dates', [{}])[0].get('games', [])
print(f"Games today: {len(games_today)}")

for game in games_today:
    home = game['teams']['home']['team']['name']
    away = game['teams']['away']['team']['name']
    home_pitcher = game['teams']['home'].get('probablePitcher', {}).get('fullName', 'TBD')
    away_pitcher = game['teams']['away'].get('probablePitcher', {}).get('fullName', 'TBD')
    print(f"  {away} @ {home}: {away_pitcher} vs {home_pitcher}")