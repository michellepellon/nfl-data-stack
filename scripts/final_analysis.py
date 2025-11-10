#!/usr/bin/env python3
"""Final analysis of the discrepancy."""

import pandas as pd
import numpy as np

schedule = pd.read_parquet('data/data_catalog/nfl_schedules.parquet')
results = pd.read_parquet('data/data_catalog/nfl_latest_results.parquet')
ratings = pd.read_parquet('data/data_catalog/nfl_ratings.parquet')

teams = ['Indianapolis Colts', 'Houston Texans']

print("=" * 80)
print("FINAL ROOT CAUSE ANALYSIS")
print("=" * 80)

for team in teams:
    current_elo = ratings[ratings['team'] == team].iloc[0]['elo_rating']

    # Past results
    past_games = results[(results['home_team'] == team) | (results['visiting_team'] == team)]
    wins = len(past_games[past_games['winning_team'] == team])
    losses = len(past_games) - wins

    # Future schedule
    future_games = schedule[
        ((schedule['home_team'] == team) | (schedule['visiting_team'] == team)) &
        (schedule['week_number'] > 10)
    ].sort_values('week_number')

    print(f"\n{team}:")
    print(f"  Current Record: {wins}-{losses} ({len(past_games)} games played)")
    print(f"  Current ELO: {current_elo:.1f}")
    print(f"  Remaining Games: {len(future_games)}")

    # Calculate expected wins in remaining games based on ELO
    expected_future_wins = 0
    print(f"\n  Future Schedule (Expected Win Prob based on current ELO):")

    for _, game in future_games.iterrows():
        is_home = game['home_team'] == team
        opponent = game['visiting_team'] if is_home else game['home_team']
        opponent_elo_col = 'visiting_team_elo_rating' if is_home else 'home_team_elo_rating'
        opponent_elo = game[opponent_elo_col]

        # Calculate win probability using ELO formula
        # P(win) = 1 / (1 + 10^(-(our_elo - opp_elo - home_adv) / 400))
        home_adv = 52 if is_home else -52
        elo_diff = current_elo - opponent_elo + home_adv
        win_prob = 1 / (1 + 10**(-(elo_diff) / 400))

        expected_future_wins += win_prob

        print(f"    Week {game['week_number']:2d} vs {opponent[:25]:25s} {'(H)' if is_home else '(A)'}: {win_prob*100:5.1f}% (Opp ELO: {opponent_elo:.0f})")

    total_expected_wins = wins + expected_future_wins

    print(f"\n  Expected Total Wins: {wins} (actual) + {expected_future_wins:.1f} (expected) = {total_expected_wins:.1f}")

print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)

colts_data = ratings[ratings['team'] == 'Indianapolis Colts'].iloc[0]
texans_data = ratings[ratings['team'] == 'Houston Texans'].iloc[0]

print(f"\nWith nearly identical ELO ratings ({colts_data['elo_rating']:.0f} vs {texans_data['elo_rating']:.0f}),")
print("teams should have similar expected future performance.")
print("\nIf the model shows significantly different projected wins despite similar ELOs,")
print("the issue is likely in how the simulation accounts for already-played games.")

print("\n" + "=" * 80)
