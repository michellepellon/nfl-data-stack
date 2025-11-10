#!/usr/bin/env python3
"""Check what columns are being displayed."""

import pandas as pd

# Read playoff probabilities
playoff_probs = pd.read_parquet('data/data_catalog/nfl_playoff_probabilities_ci.parquet')

# Filter for Colts and Texans
teams = ['Indianapolis Colts', 'Houston Texans']
data = playoff_probs[playoff_probs['team'].isin(teams)].sort_values('team')

print("=" * 80)
print("ALL COLUMNS FOR COLTS/TEXANS")
print("=" * 80)

for _, row in data.iterrows():
    print(f"\n{row['team']}:")
    print(f"  ELO: {row['elo_rating']:.1f}")
    print(f"  Playoff Prob: {row['playoff_prob_pct']:.1f}%")
    print(f"  Avg Wins (projected): {row['avg_wins']:.1f}")
    print(f"  Wins CI: {row['wins_ci_lower']:.1f} - {row['wins_ci_upper']:.1f}")

# Check if there's a vegas_win_total column
print("\n" + "=" * 80)
print("CHECKING FOR VEGAS WIN TOTAL")
print("=" * 80)

if 'vegas_win_total' in playoff_probs.columns:
    print("\nVegas win totals found in playoff probabilities:")
    for _, row in data.iterrows():
        print(f"  {row['team']}: {row['vegas_win_total']:.1f}")
else:
    print("\nNo vegas_win_total column in playoff_probabilities_ci")
    print("\nChecking nfl_ratings for vegas totals...")

    ratings = pd.read_parquet('data/data_catalog/nfl_ratings.parquet')
    ratings_filtered = ratings[ratings['team'].isin(teams)]

    if 'vegas_win_total' in ratings.columns:
        print("\nVegas win totals from nfl_ratings:")
        for _, row in ratings_filtered.iterrows():
            print(f"  {row['team']}: {row['vegas_win_total']:.1f}")

print("\n" + "=" * 80)
