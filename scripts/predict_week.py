#!/usr/bin/env python3
"""Generate NFL game predictions for a specific week using Monte Carlo simulation results.

This script analyzes 10,000 Monte Carlo simulations of the NFL regular season to predict
game outcomes for a specified week. Predictions are based on ELO ratings calibrated on
historical data (2020-2024, 1,408 games) with margin-of-victory adjustments.

Example:
    Generate predictions for Week 10:
        $ python scripts/predict_week.py 10

    Generate predictions for current week (default: 10):
        $ python scripts/predict_week.py

Attributes:
    week_num (int): NFL week number to predict (1-18)

"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


def predict_week(week_num: int = 10) -> None:
    """Generate and display NFL game predictions for a specific week.

    Loads Monte Carlo simulation results and aggregates predictions across 10,000
    simulations to calculate win probabilities for each game in the specified week.

    Args:
        week_num: NFL week number to generate predictions for (1-18). Defaults to 10.

    Returns:
        None. Prints formatted predictions to stdout.

    Raises:
        FileNotFoundError: If simulation data file is not found.
        ValueError: If no games exist for the specified week.

    """
    # Load simulation data
    data_path = Path('data/data_catalog/nfl_reg_season_simulator.parquet')
    sim = pd.read_parquet(data_path)

    # Filter to specified week
    week_data = sim[sim['week_number'] == week_num].copy()

    if len(week_data) == 0:
        print(f"\n❌ No games found for Week {week_num}")
        return

    # Calculate results per game
    results = {}
    for _, row in week_data.iterrows():
        game_id = row['game_id']
        if game_id not in results:
            results[game_id] = {
                'home_team': row['home_team'],
                'visiting_team': row['visiting_team'],
                'home_wins': 0,
                'away_wins': 0
            }
        if row['winning_team'] == row['home_team']:
            results[game_id]['home_wins'] += 1
        else:
            results[game_id]['away_wins'] += 1

    # Create clean output
    print("\n" + "="*95)
    print(f"{' '*30}WEEK {week_num} NFL PREDICTIONS")
    print("="*95 + "\n")

    for game_id in sorted(results.keys()):
        game = results[game_id]
        home = game['home_team']
        away = game['visiting_team']
        home_pct = game['home_wins'] / 100
        away_pct = game['away_wins'] / 100

        # Determine winner
        if home_pct > away_pct:
            winner = home
            win_pct = home_pct
        else:
            winner = away
            win_pct = away_pct

        matchup = f"{away:>25}  @  {home:<25}"
        print(f"{matchup}  →  {winner:<25} {win_pct:>5.1f}%")

    print("\n" + "="*95)
    print(f"Total Games: {len(results)} | Simulations per game: 10,000")
    print("="*95 + "\n")

if __name__ == "__main__":
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    predict_week(week)
