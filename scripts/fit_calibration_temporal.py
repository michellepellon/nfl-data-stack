#!/usr/bin/env python3
"""
Temporal Walk-Forward Calibration

Implements proper walk-forward validation for isotonic regression calibration.
Instead of fitting on all data at once, this script:
1. Trains on weeks 1 to N
2. Validates on week N+1
3. Tracks out-of-sample performance

This prevents overfitting and provides honest estimates of calibration improvement.

Usage:
    python scripts/fit_calibration_temporal.py

Output:
    models/elo_calibration_temporal.pkl - Fitted model (on all available data)
    data/data_catalog/calibration_validation.parquet - Per-week validation metrics
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from datetime import datetime
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss


def load_truth_set() -> pd.DataFrame:
    """Load historical predictions with actual outcomes."""
    data_path = Path("data/data_catalog/nfl_truth_set.parquet")

    if not data_path.exists():
        raise FileNotFoundError(
            f"Truth set not found at {data_path}. Run 'just build' first."
        )

    df = pd.read_parquet(data_path)
    df = df[df["game_completed"] == True].copy()

    # Compute raw home win probability from ELO
    home_adv = 48
    df["raw_prob"] = 1.0 / (
        1.0
        + 10.0
        ** (-(df["home_elo_pre_game"] - df["away_elo_pre_game"] + home_adv) / 400.0)
    )
    df["actual"] = df["home_team_won"].astype(float)

    return df


def walk_forward_calibration(
    df: pd.DataFrame, min_train_weeks: int = 4
) -> pd.DataFrame:
    """
    Perform walk-forward calibration validation.

    For each week N >= min_train_weeks:
    - Train isotonic regression on weeks 1 to N-1
    - Validate on week N
    - Track performance metrics

    Args:
        df: DataFrame with raw_prob, actual, and week_number columns
        min_train_weeks: Minimum weeks of training data before validation starts

    Returns:
        DataFrame with per-week validation metrics
    """
    weeks = sorted(df["week_number"].unique())
    results = []

    for test_week in weeks:
        if test_week < min_train_weeks + 1:
            continue

        # Split data: train on all weeks before test_week
        train_mask = df["week_number"] < test_week
        test_mask = df["week_number"] == test_week

        train_df = df[train_mask]
        test_df = df[test_mask]

        if len(train_df) < 20 or len(test_df) == 0:
            continue

        # Fit isotonic regression on training data
        iso_reg = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso_reg.fit(train_df["raw_prob"].values, train_df["actual"].values)

        # Predict on test data
        test_raw = test_df["raw_prob"].values
        test_actual = test_df["actual"].values
        test_calibrated = iso_reg.predict(test_raw)

        # Calculate metrics
        raw_brier = brier_score_loss(test_actual, test_raw)
        cal_brier = brier_score_loss(test_actual, test_calibrated)

        raw_logloss = log_loss(
            test_actual, np.clip(test_raw, 0.001, 0.999), labels=[0, 1]
        )
        cal_logloss = log_loss(
            test_actual, np.clip(test_calibrated, 0.001, 0.999), labels=[0, 1]
        )

        raw_accuracy = np.mean(
            ((test_raw > 0.5) & (test_actual == 1))
            | ((test_raw <= 0.5) & (test_actual == 0))
        )
        cal_accuracy = np.mean(
            ((test_calibrated > 0.5) & (test_actual == 1))
            | ((test_calibrated <= 0.5) & (test_actual == 0))
        )

        results.append(
            {
                "week_number": test_week,
                "n_train_games": len(train_df),
                "n_test_games": len(test_df),
                "raw_brier": raw_brier,
                "calibrated_brier": cal_brier,
                "brier_improvement": raw_brier - cal_brier,
                "raw_logloss": raw_logloss,
                "calibrated_logloss": cal_logloss,
                "logloss_improvement": raw_logloss - cal_logloss,
                "raw_accuracy": raw_accuracy,
                "calibrated_accuracy": cal_accuracy,
                "accuracy_improvement": cal_accuracy - raw_accuracy,
            }
        )

    return pd.DataFrame(results)


def fit_final_model(df: pd.DataFrame) -> IsotonicRegression:
    """Fit final isotonic regression model on all available data."""
    iso_reg = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso_reg.fit(df["raw_prob"].values, df["actual"].values)
    return iso_reg


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
    print("Temporal Walk-Forward Calibration")
    print("=" * 80 + "\n")

    # Load data
    df = load_truth_set()
    print(f"Loaded {len(df)} completed games")
    print(f"Weeks: {df['week_number'].min()} to {df['week_number'].max()}")
    print()

    # Walk-forward validation
    print("-" * 80)
    print("Walk-Forward Validation Results")
    print("-" * 80 + "\n")

    validation_df = walk_forward_calibration(df, min_train_weeks=4)

    if len(validation_df) == 0:
        print("Not enough data for walk-forward validation (need > 4 weeks)")
        print("Fitting model on all available data...\n")
    else:
        # Print per-week results
        print(
            f"{'Week':<8} {'Train':<8} {'Test':<6} {'Raw Brier':<12} {'Cal Brier':<12} {'Improve':<10}"
        )
        print("-" * 60)

        for _, row in validation_df.iterrows():
            print(
                f"{row['week_number']:<8.0f} {row['n_train_games']:<8.0f} "
                f"{row['n_test_games']:<6.0f} {row['raw_brier']:<12.4f} "
                f"{row['calibrated_brier']:<12.4f} {row['brier_improvement']:<+10.4f}"
            )

        # Summary statistics
        print("\n" + "-" * 80)
        print("Summary (Out-of-Sample)")
        print("-" * 80)

        print(f"\n{'Metric':<25} {'Mean':<15} {'Std':<15}")
        print("-" * 55)
        print(
            f"{'Brier Improvement':<25} {validation_df['brier_improvement'].mean():<+15.4f} "
            f"{validation_df['brier_improvement'].std():<15.4f}"
        )
        print(
            f"{'LogLoss Improvement':<25} {validation_df['logloss_improvement'].mean():<+15.4f} "
            f"{validation_df['logloss_improvement'].std():<15.4f}"
        )
        print(
            f"{'Accuracy Improvement':<25} {validation_df['accuracy_improvement'].mean():<+15.4f} "
            f"{validation_df['accuracy_improvement'].std():<15.4f}"
        )

        # Save validation results
        validation_path = Path("data/data_catalog/calibration_validation.parquet")
        validation_df.to_parquet(validation_path, index=False)
        print(f"\nValidation metrics saved to: {validation_path}")

    # Fit final model on all data
    print("\n" + "-" * 80)
    print("Fitting Final Model (All Data)")
    print("-" * 80)

    iso_reg = fit_final_model(df)

    # Evaluate final model (in-sample, for comparison)
    raw_probs = df["raw_prob"].values
    actuals = df["actual"].values
    calibrated = iso_reg.predict(raw_probs)

    in_sample_raw_brier = brier_score_loss(actuals, raw_probs)
    in_sample_cal_brier = brier_score_loss(actuals, calibrated)

    print(f"\nIn-sample metrics (for reference only):")
    print(f"  Raw Brier:        {in_sample_raw_brier:.4f}")
    print(f"  Calibrated Brier: {in_sample_cal_brier:.4f}")
    print(f"  Improvement:      {in_sample_raw_brier - in_sample_cal_brier:+.4f}")

    # Bin analysis
    print("\n" + "-" * 80)
    print("Calibration by Probability Bin (In-Sample)")
    print("-" * 80)

    bin_df = analyze_calibration_bins(raw_probs, calibrated, actuals)

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
    output_path = Path("models/elo_calibration_temporal.pkl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        pickle.dump(iso_reg, f)

    print(f"\n{'=' * 80}")
    print(f"Model saved to: {output_path}")
    print(f"Training games: {len(df)}")
    print(f"Fitted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if len(validation_df) > 0:
        print(f"\nOut-of-sample Brier improvement: {validation_df['brier_improvement'].mean():+.4f}")
        print("(This is the honest estimate of calibration benefit)")

    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
