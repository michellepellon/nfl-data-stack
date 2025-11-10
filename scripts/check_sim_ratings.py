#!/usr/bin/env python3
"""Check which ELO ratings are being used in the simulation."""

import pandas as pd

# Read simulation data
sim = pd.read_parquet('data/data_catalog/nfl_reg_season_simulator.parquet')
latest_elo = pd.read_parquet('data/data_catalog/nfl_latest_elo.parquet')

teams = ['Indianapolis Colts', 'Houston Texans']

print("=" * 80)
print("SIMULATION ELO RATINGS CHECK")
print("=" * 80)

print("\n1. LATEST ELO (what SHOULD be used for future games):")
print("-" * 80)
for team in teams:
    elo = latest_elo[latest_elo['team'] == team].iloc[0]['elo_rating']
    print(f"{team}: {elo:.1f}")

print("\n2. ELO RATINGS IN SIMULATION (first scenario, first future game for each team):")
print("-" * 80)

# Get first future game for each team in scenario 0
sim_sample = sim[sim['scenario_id'] == 0]

for team in teams:
    # Find the first game (future game) for this team
    team_games = sim_sample[(sim_sample['home_team'] == team) | (sim_sample['visiting_team'] == team)]

    if team_games.empty:
        print(f"\n{team}: NO GAMES IN SIMULATION")
        continue

    first_game = team_games.iloc[0]

    is_home = first_game['home_team'] == team
    elo_in_sim = first_game['home_team_elo_rating'] if is_home else first_game['visiting_team_elo_rating']

    print(f"\n{team}:")
    print(f"  Week: {first_game['week_number']}")
    print(f"  ELO in simulation: {elo_in_sim:.1f}")
    print(f"  Location: {'Home' if is_home else 'Away'}")
    print(f"  Opponent: {first_game['visiting_team'] if is_home else first_game['home_team']}")

print("\n3. ALL UNIQUE ELO RATINGS FOR THESE TEAMS IN SIMULATION:")
print("-" * 80)

for team in teams:
    home_elos = sim[sim['home_team'] == team]['home_team_elo_rating'].unique()
    away_elos = sim[sim['visiting_team'] == team]['visiting_team_elo_rating'].unique()

    all_elos = sorted(set(list(home_elos) + list(away_elos)))

    print(f"\n{team}: {len(all_elos)} unique ELO values")
    if len(all_elos) <= 5:
        for elo in all_elos:
            print(f"  {elo:.1f}")
    else:
        print(f"  Range: {min(all_elos):.1f} to {max(all_elos):.1f}")

print("\n" + "=" * 80)
