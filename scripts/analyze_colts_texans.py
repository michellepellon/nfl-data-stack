#!/usr/bin/env python3
"""Analyze Colts/Texans playoff probabilities vs projected wins."""

import pandas as pd

# Read parquet files
playoff_probs = pd.read_parquet('data/data_catalog/nfl_playoff_probabilities_ci.parquet')

# Filter for Colts and Texans using full names
teams = ['Indianapolis Colts', 'Houston Texans']
data = playoff_probs[playoff_probs['team'].isin(teams)].sort_values('team')

print("\n" + "="*80)
print("COLTS/TEXANS PLAYOFF DATA - Week 10 (Nov 9, 2025)")
print("="*80)

for _, row in data.iterrows():
    print(f"\n{row['team']} ({row['conf']}):")
    print(f"  ELO Rating: {row['elo_rating']:.0f}")
    print(f"  ")
    print(f"  Playoff Probability: {row['playoff_prob_pct']:.1f}% ({row['playoff_ci_lower_pct']:.1f}% - {row['playoff_ci_upper_pct']:.1f}%)")
    print(f"  Bye Probability: {row['bye_prob_pct']:.1f}% ({row['bye_ci_lower_pct']:.1f}% - {row['bye_ci_upper_pct']:.1f}%)")
    print(f"  Projected Wins: {row['avg_wins']:.1f} ({row['wins_ci_lower']:.1f} - {row['wins_ci_upper']:.1f})")
    print(f"  Avg Seed: {row['avg_seed']:.1f} ({row['seed_ci_lower']:.1f} - {row['seed_ci_upper']:.1f})")

print("\n" + "="*80)
print("ANALYSIS:")
print("="*80)

texans = data[data['team'] == 'Houston Texans'].iloc[0]
colts = data[data['team'] == 'Indianapolis Colts'].iloc[0]

elo_diff = texans['elo_rating'] - colts['elo_rating']
win_diff = texans['avg_wins'] - colts['avg_wins']
playoff_diff = texans['playoff_prob_pct'] - colts['playoff_prob_pct']
seed_diff = colts['avg_seed'] - texans['avg_seed']  # Lower is better

print(f"\nTexans vs Colts:")
print(f"  ELO Advantage: {elo_diff:+.0f} points")
print(f"  Projected Win Advantage: {win_diff:+.1f} wins")
print(f"  Playoff Probability Advantage: {playoff_diff:+.1f}%")
print(f"  Avg Seed (Texans): {texans['avg_seed']:.2f}  (Colts): {colts['avg_seed']:.2f}")
print()

# Check if there's a discrepancy
if win_diff > 0.5 and playoff_diff < -2:
    print("ISSUE DETECTED:")
    print(f"  Texans project to win {win_diff:.1f} MORE games than Colts,")
    print(f"  but have {abs(playoff_diff):.1f}% LOWER playoff odds!")
    print()
    print("Likely explanations:")
    print("  1. Division winner dynamics (Colts win AFC South more often)")
    print("  2. Tiebreaker scenarios favoring Colts")
    print("  3. Texans finish with better record but miss wildcard spot")
elif win_diff < -0.5 and playoff_diff > 2:
    print("ISSUE DETECTED:")
    print(f"  Colts project to win {abs(win_diff):.1f} MORE games than Texans,")
    print(f"  but have {abs(playoff_diff):.1f}% LOWER playoff odds!")
else:
    print(f"Model appears consistent:")
    if abs(win_diff) < 0.5:
        print(f"  Teams have similar projected wins (diff: {win_diff:.1f})")
    if abs(playoff_diff) < 2:
        print(f"  Teams have similar playoff odds (diff: {playoff_diff:.1f}%)")

print("\n" + "="*80)
print("DETAILED BREAKDOWN:")
print("="*80)

# Show all AFC South teams
afc_south = playoff_probs[playoff_probs['team'].str.contains('Colts|Texans|Titans|Jaguars')]
print("\nAFC South Teams:")
print(afc_south[['team', 'elo_rating', 'avg_wins', 'playoff_prob_pct', 'avg_seed']].to_string(index=False))

print("\n" + "="*80)
