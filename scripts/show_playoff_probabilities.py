#!/usr/bin/env python3
"""
Display NFL Playoff Probabilities with Confidence Intervals
Usage: python scripts/show_playoff_probabilities.py
"""
import pandas as pd
import numpy as np

def wilson_ci(p, n, z=1.96):
    """Calculate Wilson score confidence interval for a proportion"""
    denominator = 1 + (z**2) / n
    center = p + (z**2) / (2 * n)
    margin = z * np.sqrt(p * (1 - p) / n + (z**2) / (4 * n**2))
    return (center - margin) / denominator, (center + margin) / denominator

def show_playoff_probabilities():
    # Load data from Parquet
    df = pd.read_parquet('data/data_catalog/nfl_reg_season_end.parquet')
    ratings = pd.read_parquet('data/data_catalog/nfl_ratings.parquet')

    # Calculate point estimates
    stats = df.groupby('winning_team').agg({
        'made_playoffs': 'mean',
        'first_round_bye': 'mean',
        'wins': ['mean', lambda x: x.quantile(0.025), lambda x: x.quantile(0.975)],
        'season_rank': ['mean', lambda x: x.quantile(0.025), lambda x: x.quantile(0.975)],
        'conf': 'first'
    }).reset_index()

    stats.columns = ['team', 'playoff_prob', 'bye_prob', 'avg_wins', 'wins_ci_lower', 'wins_ci_upper',
                     'avg_seed', 'seed_ci_lower', 'seed_ci_upper', 'conf']

    # Calculate Wilson CIs for binary outcomes
    n_scenarios = 10000
    stats['playoff_ci_lower'], stats['playoff_ci_upper'] = wilson_ci(stats['playoff_prob'], n_scenarios)
    stats['bye_ci_lower'], stats['bye_ci_upper'] = wilson_ci(stats['bye_prob'], n_scenarios)

    # Merge with ELO ratings
    stats = stats.merge(ratings[['team', 'elo_rating']], on='team', how='left')

    # Create display strings
    stats['playoff_display'] = stats.apply(
        lambda x: f"{x['playoff_prob']*100:.1f}% [{x['playoff_ci_lower']*100:.1f}% - {x['playoff_ci_upper']*100:.1f}%]",
        axis=1
    )
    stats['bye_display'] = stats.apply(
        lambda x: f"{x['bye_prob']*100:.1f}% [{x['bye_ci_lower']*100:.1f}% - {x['bye_ci_upper']*100:.1f}%]",
        axis=1
    )
    stats['wins_display'] = stats.apply(
        lambda x: f"{x['avg_wins']:.1f} [{x['wins_ci_lower']:.1f} - {x['wins_ci_upper']:.1f}]",
        axis=1
    )

    # Sort by playoff probability
    stats = stats.sort_values('playoff_prob', ascending=False)

    # Print formatted output
    print("\n" + "="*120)
    print(f"{'':^120}")
    print(f"{'NFL PLAYOFF PROBABILITIES WITH 95% CONFIDENCE INTERVALS':^120}")
    print(f"{'':^120}")
    print("="*120)
    print()

    # AFC Teams
    print(f"\n{'AFC CONFERENCE':^120}")
    print("-"*120)
    print(f"{'Team':<25} {'ELO':>6}  {'Playoff Probability':^30}  {'First Round Bye':^30}  {'Wins':^20}")
    print("-"*120)

    for _, row in stats[stats['conf'] == 'AFC'].iterrows():
        print(f"{row['team']:<25} {int(row['elo_rating']):>6}  {row['playoff_display']:^30}  {row['bye_display']:^30}  {row['wins_display']:^20}")

    # NFC Teams
    print(f"\n{'NFC CONFERENCE':^120}")
    print("-"*120)
    print(f"{'Team':<25} {'ELO':>6}  {'Playoff Probability':^30}  {'First Round Bye':^30}  {'Wins':^20}")
    print("-"*120)

    for _, row in stats[stats['conf'] == 'NFC'].iterrows():
        print(f"{row['team']:<25} {int(row['elo_rating']):>6}  {row['playoff_display']:^30}  {row['bye_display']:^30}  {row['wins_display']:^20}")

    print("\n" + "="*120)
    print(f"{'Simulations per team: 10,000 | CI Method: Wilson score (binomial) + Empirical percentiles':^120}")
    print("="*120 + "\n")

if __name__ == "__main__":
    show_playoff_probabilities()
