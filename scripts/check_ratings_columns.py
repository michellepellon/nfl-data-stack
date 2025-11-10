#!/usr/bin/env python3
import pandas as pd

ratings = pd.read_parquet('data/data_catalog/nfl_ratings.parquet')
print("Columns in nfl_ratings:")
print(ratings.columns.tolist())
print("\nSample data:")
print(ratings.head())
