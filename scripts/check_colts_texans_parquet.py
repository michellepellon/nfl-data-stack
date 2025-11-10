#!/usr/bin/env python3
"""Quick script to check Colts/Texans playoff data from parquet."""

import pandas as pd

# Read parquet files directly
playoff_probs = pd.read_parquet('data/data_catalog/nfl_playoff_probabilities_ci.parquet')
ratings = pd.read_parquet('data/data_catalog/nfl_ratings.parquet')

# Filter for Colts and Texans
teams = ['IND', 'HOU']
colts_texans = playoff_probs[playoff_probs['team'].isin(teams)].sort_values('team')

print("\n" + "="*80)
print("COLTS/TEXANS PLAYOFF DATA - Week 10 (Nov 9, 2025)")
print("="*80)

for _, row in colts_texans.iterrows():
    team_ratings = ratings[ratings['team'] == row['team']].iloc[0]

    print(f"\n{row['team']} ({row['conf']}):")
    print(f"  ELO Rating: {team_ratings['elo_rating']:.0f}")
    print(f"  Vegas Win Total: {team_ratings['vegas_win_total']:.1f}")
    print(f"  ")
    print(f"  Playoff Probability: {row['playoff_prob_pct']:.1f}% ({row['playoff_ci_lower_pct']:.1f}% - {row['playoff_ci_upper_pct']:.1f}%)")
    print(f"  Projected Wins: {row['avg_wins']:.1f} ({row['wins_ci_lower']:.1f} - {row['wins_ci_upper']:.1f})")
    print(f"  Avg Seed: {row['avg_seed']:.1f}")

print("\n" + "="*80)
print("ANALYSIS:")
print("="*80)

colts = colts_texans[colts_texans['team'] == 'IND'].iloc[0]
texans = colts_texans[colts_texans['team'] == 'HOU'].iloc[0]
colts_ratings = ratings[ratings['team'] == 'IND'].iloc[0]
texans_ratings = ratings[ratings['team'] == 'HOU'].iloc[0]

elo_diff = texans_ratings['elo_rating'] - colts_ratings['elo_rating']
vegas_diff = texans_ratings['vegas_win_total'] - colts_ratings['vegas_win_total']
win_diff = texans['avg_wins'] - colts['avg_wins']
playoff_diff = texans['playoff_prob_pct'] - colts['playoff_prob_pct']

print(f"\nTexans vs Colts:")
print(f"  ELO Advantage: +{elo_diff:.0f} points")
print(f"  Vegas Win Total Advantage: +{vegas_diff:.1f} wins")
print(f"  Projected Win Advantage: +{win_diff:.1f} wins")
print(f"  Playoff Probability Advantage: {playoff_diff:+.1f}%")
print()

if win_diff > 0 and playoff_diff < 0:
    print("ISSUE DETECTED:")
    print(f"  Texans project to win {win_diff:.1f} MORE games than Colts,")
    print(f"  but have {abs(playoff_diff):.1f}% LOWER playoff odds!")
    print()
    print("Possible explanations:")
    print("  1. Division winner dynamics (Colts win AFC South more often)")
    print("  2. Tiebreaker scenarios favoring Colts")
    print("  3. Schedule strength differences in remaining games")
elif win_diff < 0 and playoff_diff > 0:
    print("ISSUE DETECTED:")
    print(f"  Colts project to win {abs(win_diff):.1f} MORE games than Texans,")
    print(f"  but have {abs(playoff_diff):.1f}% LOWER playoff odds!")
else:
    print(f"Model appears consistent - team with more projected wins has higher playoff odds.")

print("\n" + "="*80)
