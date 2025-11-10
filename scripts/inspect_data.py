#!/usr/bin/env python3
"""Inspect playoff probabilities data."""

import pandas as pd

# Read parquet files
playoff_probs = pd.read_parquet('data/data_catalog/nfl_playoff_probabilities_ci.parquet')
print("Playoff Probabilities Shape:", playoff_probs.shape)
print("\nColumns:", playoff_probs.columns.tolist())
print("\nFirst few rows:")
print(playoff_probs.head())

print("\n\nAll teams:")
print(playoff_probs['team'].unique())

print("\n\nFilter for IND and HOU:")
colts_texans = playoff_probs[playoff_probs['team'].isin(['IND', 'HOU'])]
print(colts_texans)
