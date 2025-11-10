#!/usr/bin/env python3
"""Verify the webpage data has correct structure."""

import json
from pathlib import Path

webpage_data_path = Path(__file__).parent.parent.parent / "personal-site" / "portfolio" / "data" / "webpage_data.json"

with open(webpage_data_path) as f:
    data = json.load(f)

print("=" * 80)
print("WEBPAGE DATA VERIFICATION")
print("=" * 80)

# Check ratings structure
print("\n1. RATINGS STRUCTURE (sample):")
colts_rating = [r for r in data['ratings'] if 'Colts' in r['team']][0]
texans_rating = [r for r in data['ratings'] if 'Texans' in r['team']][0]

print(f"Colts:  {colts_rating}")
print(f"Texans: {texans_rating}")

if 'vegas_preseason_total' in colts_rating:
    print("\n✓ Field renamed to 'vegas_preseason_total' (correct)")
else:
    print("\n✗ Still using old field name")

# Check playoffs structure
print("\n2. PLAYOFFS STRUCTURE (sample):")
colts_playoff = [p for p in data['playoffs'] if 'Colts' in p['team']][0]
texans_playoff = [p for p in data['playoffs'] if 'Texans' in p['team']][0]

print(f"\nColts:")
print(f"  ELO: {colts_playoff['elo_rating']}")
print(f"  Projected Wins: {colts_playoff['avg_wins']}")
print(f"  Playoff Prob: {colts_playoff['playoff_prob_pct']}%")
print(f"  Vegas Preseason (from ratings): {colts_rating['vegas_preseason_total']}")

print(f"\nTexans:")
print(f"  ELO: {texans_playoff['elo_rating']}")
print(f"  Projected Wins: {texans_playoff['avg_wins']}")
print(f"  Playoff Prob: {texans_playoff['playoff_prob_pct']}%")
print(f"  Vegas Preseason (from ratings): {texans_rating['vegas_preseason_total']}")

print("\n" + "=" * 80)
print("VALIDATION:")
print("=" * 80)

# Validate Colts
if colts_playoff['avg_wins'] == 11.0 and colts_playoff['playoff_prob_pct'] == 84.9:
    print("✓ Colts data correct: 11.0 wins, 84.9% playoff odds")
else:
    print(f"✗ Colts data incorrect: {colts_playoff['avg_wins']} wins, {colts_playoff['playoff_prob_pct']}% playoff odds")

# Validate Texans
if texans_playoff['avg_wins'] == 8.1 and texans_playoff['playoff_prob_pct'] == 19.1:
    print("✓ Texans data correct: 8.1 wins, 19.1% playoff odds")
else:
    print(f"✗ Texans data incorrect: {texans_playoff['avg_wins']} wins, {texans_playoff['playoff_prob_pct']}% playoff odds")

print("\n" + "=" * 80)
