#!/usr/bin/env python3
"""Check ELO ratings for Colts and Texans."""

import pandas as pd

# Read the raw initial ratings
raw_ratings = pd.read_parquet('data/data_catalog/nfl_raw_team_ratings.parquet')

# Read the latest ELO after rollforward
latest_elo = pd.read_parquet('data/data_catalog/nfl_latest_elo.parquet')

# Read the actual results
results = pd.read_parquet('data/data_catalog/nfl_latest_results.parquet')

teams = ['Indianapolis Colts', 'Houston Texans']

print("=" * 80)
print("ELO RATING INVESTIGATION")
print("=" * 80)

print("\n1. INITIAL RATINGS (from nfl_raw_team_ratings):")
print("-" * 80)
for team in teams:
    rating = raw_ratings[raw_ratings['team'] == team]
    if not rating.empty:
        print(f"{team}: {rating.iloc[0]['elo_rating']:.1f}")

print("\n2. LATEST RATINGS (after rollforward through Week 10):")
print("-" * 80)
for team in teams:
    rating = latest_elo[latest_elo['team'] == team]
    if not rating.empty:
        print(f"{team}: {rating.iloc[0]['elo_rating']:.1f}")

print("\n3. ACTUAL RESULTS:")
print("-" * 80)
for team in teams:
    team_games = results[(results['home_team'] == team) | (results['visiting_team'] == team)]
    wins = len(team_games[team_games['winning_team'] == team])
    losses = len(team_games) - wins
    print(f"{team}: {wins}-{losses} ({wins}/{len(team_games)} = {wins/len(team_games)*100:.1f}%)")

print("\n4. ELO ROLLFORWARD DETAIL:")
print("-" * 80)

# Read the rollforward data to see game-by-game ELO changes
rollforward = pd.read_parquet('data/data_catalog/nfl_elo_rollforward.parquet')

for team in teams:
    print(f"\n{team}:")
    team_games = rollforward[(rollforward['home_team'] == team) | (rollforward['visiting_team'] == team)]

    if team_games.empty:
        print("  No games found in rollforward data!")
        continue

    print(f"  Games: {len(team_games)}")

    # Track ELO progression
    print("\n  Game-by-game ELO:")
    for _, game in team_games.iterrows():
        is_home = game['home_team'] == team
        elo_before = game['home_team_elo_rating'] if is_home else game['visiting_team_elo_rating']
        elo_change = -game['elo_change'] if is_home else game['elo_change']
        elo_after = elo_before + elo_change

        won = game['winning_team'] == team
        opponent = game['visiting_team'] if is_home else game['home_team']

        print(f"    Game {game['game_id']:3d}: {elo_before:7.1f} -> {elo_after:7.1f} ({elo_change:+6.1f}) vs {opponent[:20]:20s} {'W' if won else 'L'}")

print("\n" + "=" * 80)
