#!/usr/bin/env python3
"""
Generate Webpage Data for NFL ELO Prediction System

Creates webpage_data.json with calibrated model metrics for the static site.

Usage:
    python scripts/generate_webpage_data.py
"""

import duckdb
import json
from pathlib import Path
from datetime import datetime


def generate_webpage_data():
    """Generate JSON data for the static webpage using calibrated model"""
    db_path = Path(__file__).parent.parent / "data" / "data_catalog" / "nflds.duckdb"
    conn = duckdb.connect(str(db_path), read_only=True)

    # Get calibrated model performance metrics
    calibrated_perf = conn.execute("""
        SELECT * FROM nfl_calibrated_model_performance ORDER BY bin_lower
    """).df()

    if len(calibrated_perf) == 0:
        print("ERROR: No calibrated model performance data found.")
        print("Run 'cd transform && dbt build --select nfl_elo_calibrated_predictions nfl_calibrated_model_performance' first")
        return None

    # Extract overall metrics from calibrated model
    overall_metrics = calibrated_perf.iloc[0]

    data = {
        "generated_at": datetime.now().isoformat(),
        "model_version": "Calibrated ELO v1.1",
        "model_type": "isotonic_regression_calibrated",
        "overall_metrics": {
            "brier_score": float(overall_metrics["overall_brier_score"]),
            "log_loss": float(overall_metrics["overall_log_loss"]),
            "mae_pct": float(overall_metrics["overall_mae_pct"]),
            "calibration_r_squared": float(overall_metrics["calibration_r_squared"]),
            "total_games": int(overall_metrics["total_games"])
        },
        "calibration_bins": []
    }

    # Add calibration bin data
    for _, row in calibrated_perf.iterrows():
        data["calibration_bins"].append({
            "bin": row["probability_bin"],
            "bin_lower": float(row["bin_lower"]) / 100.0,
            "bin_upper": float(row["bin_upper"]) / 100.0,
            "n_games": int(row["n_games"]),
            "avg_predicted_pct": float(row["avg_predicted_pct"]),
            "actual_win_rate_pct": float(row["actual_win_rate_pct"]),
            "calibration_error_pct": float(row["calibration_error_pct"]),
            "quality": row["bin_calibration_quality"],
            "mean_predicted": float(row["avg_predicted_pct"]) / 100.0,
            "mean_observed": float(row["actual_win_rate_pct"]) / 100.0,
            "n_predictions": int(row["n_games"])
        })

    # Calculate overall accuracy from bin data
    total_correct = sum([
        int(row["n_games"]) * (float(row["actual_win_rate_pct"]) / 100.0)
        for _, row in calibrated_perf.iterrows()
    ])
    total_games = sum([int(row["n_games"]) for _, row in calibrated_perf.iterrows()])
    data["overall_metrics"]["accuracy"] = total_correct / total_games if total_games > 0 else 0

    # Quality rating based on Brier score
    brier = data["overall_metrics"]["brier_score"]
    if brier < 0.20:
        rating = "Excellent"
    elif brier < 0.25:
        rating = "Good"
    elif brier < 0.30:
        rating = "Fair"
    else:
        rating = "Needs Improvement"

    data["overall_metrics"]["rating"] = rating

    conn.close()

    return data


def main():
    print("Generating webpage data with calibrated model metrics...")

    data = generate_webpage_data()

    if data is None:
        return

    # Save to personal-site portfolio data directory
    output_path = Path(__file__).parent.parent.parent / "personal-site" / "portfolio" / "data" / "calibrated_metrics.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Generated calibrated metrics at {output_path}")
    print(f"\nMetrics Summary:")
    print(f"  Brier Score: {data['overall_metrics']['brier_score']:.4f}")
    print(f"  Log Loss: {data['overall_metrics']['log_loss']:.4f}")
    print(f"  Accuracy: {data['overall_metrics']['accuracy']*100:.1f}%")
    print(f"  Calibration R²: {data['overall_metrics']['calibration_r_squared']:.4f}")
    print(f"  Rating: {data['overall_metrics']['rating']}")
    print(f"  Total Games: {data['overall_metrics']['total_games']}")
    print(f"  Calibration Bins: {len(data['calibration_bins'])}")

    # Also print what should be displayed on webpage
    print(f"\n📊 Webpage Display Values:")
    print(f"  Accuracy: {data['overall_metrics']['accuracy']*100:.1f}%")
    print(f"  Brier Score: {data['overall_metrics']['brier_score']:.3f}")
    print(f"  Log Loss: {data['overall_metrics']['log_loss']:.3f}")
    print(f"  Rating: {data['overall_metrics']['rating'].upper()}")


if __name__ == "__main__":
    main()
