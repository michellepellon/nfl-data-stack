#!/usr/bin/env python3

import pandas as pd

schedule = pd.read_parquet('data/data_catalog/nfl_schedules.parquet')
sim = pd.read_parquet('data/data_catalog/nfl_reg_season_simulator.parquet')
results = pd.read_parquet('data/data_catalog/nfl_latest_results.parquet')

print("Schedule columns:", schedule.columns.tolist())
print("\nSimulation columns:", sim.columns.tolist())
print("\nResults columns:", results.columns.tolist())

print("\n\nSchedule sample:")
print(schedule.head())
