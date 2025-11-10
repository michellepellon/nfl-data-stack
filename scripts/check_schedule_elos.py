#!/usr/bin/env python3
"""Check what ELO ratings are in the schedule."""

import pandas as pd

schedule = pd.read_parquet('data/data_catalog/nfl_schedules.parquet')
latest_elo = pd.read_parquet('data/data_catalog/nfl_latest_elo.parquet')

teams = ['Indianapolis Colts', 'Houston Texans']

print("=" * 80)
print("SCHEDULE ELO RATINGS CHECK")
print("="  * 80)

print("\n1. CURRENT LATEST ELO (should be used for future games):")
print("-" * 80)
for team in teams:
    elo = latest_elo[latest_elo['team'] == team].iloc[0]['elo_rating']
    print(f"{team}: {elo:.1f}")

print("\n2. FIRST FUTURE GAME IN SCHEDULE FOR EACH TEAM:")
print("-" * 80)

for team in teams:
    # Future games (week > 10)
    future_games = schedule[
        ((schedule['home_team'] == team) | (schedule['visiting_team'] == team)) &
        (schedule['week_number'] > 10)
    ].sort_values('week_number')

    if future_games.empty:
        print(f"\n{team}: NO FUTURE GAMES")
        continue

    first_game = future_games.iloc[0]
    is_home = first_game['home_team'] == team
    elo_in_schedule = first_game['home_team_elo_rating'] if is_home else first_game['visiting_team_elo_rating']

    print(f"\n{team}:")
    print(f"  Week: {first_game['week_number']}")
    print(f"  ELO in schedule: {elo_in_schedule:.1f}")
    print(f"  Location: {'Home' if is_home else 'Away'}")
    print(f"  Opponent: {first_game['visiting_team'] if is_home else first_game['home_team']}")

print("\n3. ALL GAMES FOR TEAMS (showing ELO ratings):")
print("-" * 80)

for team in teams:
    print(f"\n{team}:")
    team_games = schedule[
        (schedule['home_team'] == team) | (schedule['visiting_team'] == team)
    ].sort_values('week_number')

    for _, game in team_games.iterrows():
        is_home = game['home_team'] == team
        elo = game['home_team_elo_rating'] if is_home else game['visiting_team_elo_rating']
        opponent = game['visiting_team'] if is_home else game['home_team']

        print(f"  Week {game['week_number']:2d}: ELO={elo:7.1f} vs {opponent[:25]:25s} {'(H)' if is_home else '(A)'}")

print("\n" + "=" * 80)
