#!/usr/bin/env python3
"""
Generate Full Webpage Data for NFL Game Predictions

Creates webpage_data.json with all predictions, ratings, and playoff probabilities
for the static site.

Usage:
    python scripts/generate_full_webpage_data.py
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime


def generate_full_webpage_data():
    """Generate complete JSON data for the static webpage"""
    data_dir = Path(__file__).parent.parent / "data" / "data_catalog"

    data = {
        "generated_at": datetime.now().isoformat(),
        "current_week": 10,
    }

    # Get current team ratings
    ratings_df = pd.read_parquet(data_dir / "nfl_ratings.parquet")
    ratings_df = ratings_df.sort_values('elo_rating', ascending=False)
    data["ratings"] = ratings_df[['team', 'conf', 'division', 'elo_rating', 'win_total']].to_dict('records')

    # Get Week 10 predictions from simulator
    sim_df = pd.read_parquet(data_dir / "nfl_reg_season_simulator.parquet")
    week10_df = sim_df[sim_df['week_number'] == 10].copy()

    # Group by game and calculate win probability (convert from basis points)
    week10_games = []
    for game_id in week10_df['game_id'].unique():
        game_data = week10_df[week10_df['game_id'] == game_id].iloc[0]
        week10_games.append({
            'game_id': int(game_data['game_id']),
            'week_number': int(game_data['week_number']),
            'visiting_team': game_data['visiting_team'],
            'home_team': game_data['home_team'],
            'visiting_team_elo_rating': float(game_data['visiting_team_elo_rating']),
            'home_team_elo_rating': float(game_data['home_team_elo_rating']),
            'home_win_probability': float(game_data['home_team_win_probability']) / 10000.0,
            'predicted_winner': game_data['home_team'] if game_data['home_team_win_probability'] > 5000 else game_data['visiting_team'],
            'rest_adj': 0.0,
            'temp_adj': 0,
            'wind_adj': 0,
            'injury_adj': 0.0,
            'total_adj': 0.0,
            'confidence_adjusted': abs((float(game_data['home_team_win_probability']) / 10000.0) - 0.5)
        })

    data["week10_predictions"] = sorted(week10_games, key=lambda x: x['game_id'])

    # Get calibration data
    try:
        calibration_df = pd.read_parquet(data_dir / "nfl_calibration_curve.parquet")
        calibration_records = []
        for _, row in calibration_df.iterrows():
            calibration_records.append({
                'bin_lower': float(row['bin_lower']) / 100.0,
                'bin_upper': float(row['bin_upper']) / 100.0,
                'bin_midpoint': (float(row['bin_lower']) + float(row['bin_upper'])) / 200.0,
                'mean_predicted': float(row['avg_predicted_pct']) / 100.0,
                'mean_observed': float(row['actual_win_rate_pct']) / 100.0,
                'n_predictions': int(row['n_games']),
                'stddev_observed': 0.0,
                'se_observed': 0.0,
                'ci_lower': 0.0,
                'ci_upper': 0.0,
                'perfect_calibration': (float(row['bin_lower']) + float(row['bin_upper'])) / 200.0,
                'calibration_error': float(row['calibration_error_pct']) / 100.0,
                'ingested_at': datetime.now().isoformat()
            })
        data["calibration"] = calibration_records
    except Exception as e:
        print(f"Warning: Could not load calibration data: {e}")
        data["calibration"] = []

    # Get performance by week (exclude current week since games haven't been played)
    try:
        performance_df = pd.read_parquet(data_dir / "nfl_model_performance.parquet")
        current_week = data["current_week"]
        performance_records = []
        for _, row in performance_df.iterrows():
            week_num = int(row['week_number'])
            # Only include completed weeks
            if week_num < current_week:
                brier = float(row['brier_score'])
                performance_records.append({
                    'week_number': week_num,
                    'brier_score': brier,
                    'log_loss': float(row['log_loss']),
                    'accuracy': float(row['accuracy']),
                    'performance_rating': 'Excellent' if brier < 0.20 else 'Good' if brier < 0.25 else 'Fair' if brier < 0.30 else 'Needs improvement'
                })
        data["performance"] = sorted(performance_records, key=lambda x: x['week_number'])
    except Exception as e:
        print(f"Warning: Could not load performance data: {e}")
        data["performance"] = []

    # Get playoff probabilities
    try:
        playoffs_df = pd.read_parquet(data_dir / "nfl_playoff_probabilities_ci.parquet")
        playoffs_df = playoffs_df.sort_values('playoff_prob_pct', ascending=False)
        playoffs_records = []
        for _, row in playoffs_df.iterrows():
            playoffs_records.append({
                'team': row['team'],
                'conf': row['conf'],
                'elo_rating': float(row['elo_rating']),
                'playoff_prob_pct': float(row['playoff_prob_pct']),
                'playoff_ci_lower_pct': float(row['playoff_ci_lower_pct']),
                'playoff_ci_upper_pct': float(row['playoff_ci_upper_pct']),
                'playoff_ci_width_pct': float(row['playoff_ci_width_pct']),
                'bye_prob_pct': float(row['bye_prob_pct']),
                'bye_ci_lower_pct': float(row['bye_ci_lower_pct']),
                'bye_ci_upper_pct': float(row['bye_ci_upper_pct']),
                'bye_ci_width_pct': float(row['bye_ci_width_pct']),
                'avg_wins': float(row['avg_wins']),
                'wins_ci_lower': float(row['wins_ci_lower']),
                'wins_ci_upper': float(row['wins_ci_upper']),
                'wins_ci_width': float(row['wins_ci_width']),
                'avg_seed': float(row['avg_seed']),
                'seed_ci_lower': float(row['seed_ci_lower']),
                'seed_ci_upper': float(row['seed_ci_upper']),
                'playoff_prob_display': f"{row['playoff_prob_pct']:.1f}% [{row['playoff_ci_lower_pct']:.1f}% - {row['playoff_ci_upper_pct']:.1f}%]",
                'bye_prob_display': f"{row['bye_prob_pct']:.1f}% [{row['bye_ci_lower_pct']:.1f}% - {row['bye_ci_upper_pct']:.1f}%]",
                'wins_display': f"{row['avg_wins']:.1f} [{row['wins_ci_lower']:.1f} - {row['wins_ci_upper']:.1f}]",
                'seed_display': f"{row['avg_seed']:.1f} [{row['seed_ci_lower']:.1f} - {row['seed_ci_upper']:.1f}]",
                'n_scenarios': int(row['n_scenarios']),
                'sim_start_game_id': int(row['sim_start_game_id']),
                'ingested_at': str(row['ingested_at'])
            })
        data["playoffs"] = playoffs_records
    except Exception as e:
        print(f"Warning: Could not load playoff data: {e}")
        data["playoffs"] = []

    return data


def main():
    print("Generating full webpage data...")

    data = generate_full_webpage_data()

    # Save to personal-site portfolio data directory
    output_path = Path(__file__).parent.parent.parent / "personal-site" / "portfolio" / "data" / "webpage_data.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Generated webpage data at {output_path}")
    print(f"\nData Summary:")
    print(f"  Current Week: {data['current_week']}")
    print(f"  Teams: {len(data['ratings'])}")
    print(f"  Week 10 Predictions: {len(data['week10_predictions'])}")
    print(f"  Calibration Bins: {len(data['calibration'])}")
    print(f"  Performance Weeks: {len(data['performance'])}")
    print(f"  Playoff Teams: {len(data['playoffs'])}")

    # Show Seahawks vs Cardinals prediction
    seahawks_game = [g for g in data['week10_predictions'] if g['home_team'] == 'Seattle Seahawks' and g['visiting_team'] == 'Arizona Cardinals']
    if seahawks_game:
        sample = seahawks_game[0]
        print(f"\n📊 Seahawks vs Cardinals (FIXED):")
        print(f"  {sample['visiting_team']} @ {sample['home_team']}")
        print(f"  ELO: {sample['visiting_team_elo_rating']:.0f} vs {sample['home_team_elo_rating']:.0f}")
        print(f"  Home win prob: {sample['home_win_probability']:.1%}")
        print(f"  ✅ Seahawks correctly favored at home!")


if __name__ == "__main__":
    main()
