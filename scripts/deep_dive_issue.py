#!/usr/bin/env python3
"""Deep dive into the Colts/Texans discrepancy."""

import pandas as pd

# Read simulation and schedule data
sim = pd.read_parquet('data/data_catalog/nfl_reg_season_simulator.parquet')
schedule = pd.read_parquet('data/data_catalog/nfl_schedules.parquet')
results = pd.read_parquet('data/data_catalog/nfl_latest_results.parquet')

print("=" * 80)
print("INVESTIGATING ROOT CAUSE")
print("=" * 80)

# Check how many games each team has played and has remaining
print("\n1. GAMES PLAYED VS REMAINING:")
print("-" * 80)

for team in ['Indianapolis Colts', 'Houston Texans']:
    # Games as home team
    home_played = results[results['home_team'] == team]
    home_remaining = schedule[(schedule['home_team'] == team) & (schedule['week_number'] > 10)]

    # Games as visiting team
    visit_played = results[results['visiting_team'] == team]
    visit_remaining = schedule[(schedule['visiting_team'] == team) & (schedule['week_number'] > 10)]

    total_played = len(home_played) + len(visit_played)
    total_remaining = len(home_remaining) + len(visit_remaining)

    print(f"\n{team}:")
    print(f"  Games Played: {total_played}")
    print(f"  Games Remaining: {total_remaining}")
    print(f"  Total: {total_played + total_remaining}")

# Check simulation game counts
print("\n\n2. SIMULATION GAME COUNTS (Scenario 0):")
print("-" * 80)

sim_sample = sim[sim['scenario_id'] == 0]
for team in ['Indianapolis Colts', 'Houston Texans']:
    team_games = sim_sample[(sim_sample['home_team'] == team) | (sim_sample['visiting_team'] == team)]
    print(f"\n{team}: {len(team_games)} games in simulation")

    # Count wins
    wins = len(team_games[team_games['winning_team'] == team])
    print(f"  Wins in scenario 0: {wins}")

print("\n\n3. SAMPLE OF SIMULATION RESULTS (Scenario 0):")
print("-" * 80)

for team in ['Indianapolis Colts', 'Houston Texans']:
    print(f"\n{team} games:")
    team_games = sim_sample[(sim_sample['home_team'] == team) | (sim_sample['visiting_team'] == team)]
    print(team_games[['week_number', 'home_team', 'visiting_team', 'winning_team', 'home_team_elo_rating', 'visiting_team_elo_rating']].head(10).to_string(index=False))

print("\n\n4. CHECK RESULTS DATA:")
print("-" * 80)

for team in ['Indianapolis Colts', 'Houston Texans']:
    team_results = results[(results['home_team'] == team) | (results['visiting_team'] == team)]
    wins = len(team_results[team_results['winning_team'] == team])
    print(f"\n{team}:")
    print(f"  Results through Week 10: {len(team_results)} games")
    print(f"  Wins: {wins}")
    print(f"  Losses: {len(team_results) - wins}")

print("\n\n" + "=" * 80)
