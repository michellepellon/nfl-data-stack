#!/usr/bin/env python3
"""
Fit Isotonic Regression Calibration Model

Trains an isotonic regression model on historical ELO predictions to calibrate
future win probabilities. The calibrated model corrects systematic biases
(e.g., overconfidence in high-probability predictions).

Usage:
    python scripts/fit_calibration.py

Output:
    models/elo_calibration.pkl - Fitted IsotonicRegression model
"""

import pandas as pd
import pickle
from pathlib import Path
from datetime import datetime
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss
import numpy as np


def load_prediction_data() -> pd.DataFrame:
    """Load historical predictions with actual outcomes."""
    data_path = Path("data/data_catalog/nfl_truth_set.parquet")

    if not data_path.exists():
        raise FileNotFoundError(
            f"Truth set not found at {data_path}. Run 'just build' first."
        )

    df = pd.read_parquet(data_path)
    print(f"Loaded {len(df)} games from truth set")

    return df


def fit_isotonic_calibration(
    predictions: np.ndarray, outcomes: np.ndarray
) -> IsotonicRegression:
    """
    Fit isotonic regression for probability calibration.

    Isotonic regression finds a monotonically increasing function that minimizes
    MSE between predicted and actual probabilities. This corrects for systematic
    calibration errors while preserving the ranking of predictions.

    Args:
        predictions: Raw predicted probabilities (0-1)
        outcomes: Actual binary outcomes (0 or 1)

    Returns:
        Fitted IsotonicRegression model
    """
    iso_reg = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso_reg.fit(predictions, outcomes)

    return iso_reg


def evaluate_calibration(
    predictions: np.ndarray,
    calibrated: np.ndarray,
    outcomes: np.ndarray,
) -> dict:
    """Evaluate calibration improvement."""
    results = {
        "raw_brier": brier_score_loss(outcomes, predictions),
        "calibrated_brier": brier_score_loss(outcomes, calibrated),
        "raw_log_loss": log_loss(outcomes, np.clip(predictions, 0.001, 0.999)),
        "calibrated_log_loss": log_loss(outcomes, np.clip(calibrated, 0.001, 0.999)),
    }

    results["brier_improvement"] = results["raw_brier"] - results["calibrated_brier"]
    results["log_loss_improvement"] = (
        results["raw_log_loss"] - results["calibrated_log_loss"]
    )

    return results


def analyze_calibration_bins(
    predictions: np.ndarray,
    calibrated: np.ndarray,
    outcomes: np.ndarray,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Analyze calibration by probability bin."""
    bins = np.linspace(0, 1, n_bins + 1)
    bin_data = []

    for i in range(n_bins):
        mask = (predictions >= bins[i]) & (predictions < bins[i + 1])
        if mask.sum() == 0:
            continue

        bin_preds = predictions[mask]
        bin_cal = calibrated[mask]
        bin_outcomes = outcomes[mask]

        bin_data.append(
            {
                "bin_lower": bins[i],
                "bin_upper": bins[i + 1],
                "n_games": mask.sum(),
                "raw_mean_pred": bin_preds.mean(),
                "calibrated_mean_pred": bin_cal.mean(),
                "actual_rate": bin_outcomes.mean(),
                "raw_error": abs(bin_preds.mean() - bin_outcomes.mean()),
                "calibrated_error": abs(bin_cal.mean() - bin_outcomes.mean()),
            }
        )

    return pd.DataFrame(bin_data)


def main():
    print("\n" + "=" * 80)
    print("Fitting Isotonic Regression Calibration Model")
    print("=" * 80 + "\n")

    # Load data
    df = load_prediction_data()

    # Filter to completed games only
    df = df[df["game_completed"] == True].copy()
    print(f"Completed games: {len(df)}")

    # Extract predictions and outcomes
    # Truth set has home_elo_pre_game, away_elo_pre_game, home_team_won
    home_adv = 48  # Default home advantage

    # Compute home win probability from ELO ratings
    df["home_win_prob"] = 1.0 / (
        1.0
        + 10.0
        ** (
            -(df["home_elo_pre_game"] - df["away_elo_pre_game"] + home_adv)
            / 400.0
        )
    )

    # Use home_team_won as outcome
    df["home_win"] = df["home_team_won"].astype(int)

    predictions = df["home_win_prob"].values
    outcomes = df["home_win"].values

    print(f"Training data: {len(predictions)} games")
    print(f"Home win rate: {outcomes.mean():.1%}")
    print(f"Mean predicted: {predictions.mean():.1%}")
    print()

    # Fit isotonic regression
    print("Fitting isotonic regression...")
    iso_reg = fit_isotonic_calibration(predictions, outcomes)

    # Get calibrated predictions
    calibrated = iso_reg.predict(predictions)

    # Evaluate improvement
    print("\n" + "-" * 80)
    print("Calibration Results")
    print("-" * 80)

    metrics = evaluate_calibration(predictions, calibrated, outcomes)

    print(f"\n{'Metric':<25} {'Raw':<15} {'Calibrated':<15} {'Improvement':<15}")
    print("-" * 70)
    print(
        f"{'Brier Score':<25} {metrics['raw_brier']:<15.4f} {metrics['calibrated_brier']:<15.4f} {metrics['brier_improvement']:<+15.4f}"
    )
    print(
        f"{'Log Loss':<25} {metrics['raw_log_loss']:<15.4f} {metrics['calibrated_log_loss']:<15.4f} {metrics['log_loss_improvement']:<+15.4f}"
    )

    # Bin analysis
    print("\n" + "-" * 80)
    print("Calibration by Probability Bin")
    print("-" * 80)

    bin_df = analyze_calibration_bins(predictions, calibrated, outcomes)

    print(
        f"\n{'Bin':<12} {'N':<8} {'Raw Pred':<12} {'Cal Pred':<12} {'Actual':<12} {'Raw Err':<12} {'Cal Err':<12}"
    )
    print("-" * 80)

    for _, row in bin_df.iterrows():
        bin_label = f"{row['bin_lower']:.0%}-{row['bin_upper']:.0%}"
        print(
            f"{bin_label:<12} {row['n_games']:<8.0f} {row['raw_mean_pred']:<12.1%} "
            f"{row['calibrated_mean_pred']:<12.1%} {row['actual_rate']:<12.1%} "
            f"{row['raw_error']:<12.1%} {row['calibrated_error']:<12.1%}"
        )

    # Save model
    output_path = Path("models/elo_calibration.pkl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        pickle.dump(iso_reg, f)

    print(f"\n{'=' * 80}")
    print(f"Model saved to: {output_path}")
    print(f"Training games: {len(predictions)}")
    print(f"Fitted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
