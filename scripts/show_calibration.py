#!/usr/bin/env python3
"""
Display ELO Calibration Analysis
Usage: python scripts/show_calibration.py
"""
import pandas as pd
import duckdb

def show_calibration():
    # Load calibration data from DuckDB
    conn = duckdb.connect('data/data_catalog/nflds.duckdb', read_only=True)
    df = conn.execute("SELECT * FROM nfl_elo_calibration ORDER BY bin_lower").df()
    conn.close()

    if len(df) == 0:
        print("\n❌ No calibration data available. Run `just build` first.\n")
        return

    # Get overall metrics (same for all rows)
    overall = df.iloc[0]

    print("\n" + "="*120)
    print(f"{'ELO CALIBRATION ANALYSIS':^120}")
    print("="*120 + "\n")

    # Overall Metrics
    print(f"{'OVERALL PREDICTION QUALITY':^120}")
    print("-"*120)
    print(f"{'Metric':<40} {'Value':<20} {'Assessment':<60}")
    print("-"*120)

    # Brier Score
    brier = overall['overall_brier_score']
    brier_assessment = "Excellent" if brier < 0.20 else "Good" if brier < 0.25 else "Needs Improvement"
    print(f"{'Brier Score':<40} {brier:<20.4f} {brier_assessment + ' (< 0.25 is good, < 0.20 is excellent)':<60}")

    # Log Loss
    log_loss = overall['overall_log_loss']
    print(f"{'Log Loss':<40} {log_loss:<20.4f} {'Lower is better':<60}")

    # MAE
    mae = overall['overall_mae_pct']
    mae_assessment = "Excellent" if mae < 5 else "Good" if mae < 10 else "Fair" if mae < 15 else "Poor"
    print(f"{'Mean Absolute Error':<40} {mae:<20.1f}% {mae_assessment + ' (< 5% is excellent)':<60}")

    # R²
    r_squared = overall['calibration_r_squared']
    r2_assessment = "Excellent" if r_squared > 0.95 else "Good" if r_squared > 0.90 else "Fair" if r_squared > 0.80 else "Poor"
    print(f"{'Calibration R²':<40} {r_squared:<20.4f} {r2_assessment + ' (> 0.95 is excellent)':<60}")

    # Total Games
    print(f"{'Total Games Analyzed':<40} {int(overall['total_games']):<20} {'':<60}")

    # Calibration by Bin
    print(f"\n{'CALIBRATION BY PROBABILITY BIN':^120}")
    print("-"*120)
    print(f"{'Bin':<15} {'N':<8} {'Avg Predicted':<18} {'Actual Rate':<18} {'Error':<18} {'Quality':<15} {'Brier Score':<15}")
    print("-"*120)

    for _, row in df.iterrows():
        bin_name = row['probability_bin']
        n_games = int(row['n_games'])
        predicted = f"{row['avg_predicted_pct']:.1f}%"
        actual = f"{row['actual_win_rate_pct']:.1f}%"
        error = f"{row['calibration_error_pct']:.1f}%"
        quality = row['bin_calibration_quality']
        bin_brier = f"{row['bin_brier_score']:.4f}"

        print(f"{bin_name:<15} {n_games:<8} {predicted:<18} {actual:<18} {error:<18} {quality:<15} {bin_brier:<15}")

    # ASCII Calibration Plot
    print(f"\n{'CALIBRATION CURVE (Predicted vs Actual)':^120}")
    print("-"*120)
    print(f"{'Predicted %':<15} {'Actual %':<15} {'Visualization':<90}")
    print("-"*120)

    # Create simple ASCII visualization
    for _, row in df.iterrows():
        predicted_pct = row['avg_predicted_pct']
        actual_pct = row['actual_win_rate_pct']
        bin_name = row['probability_bin']

        # Create bar visualization (scale 0-100 to 0-60 chars)
        pred_bar_len = int(predicted_pct * 0.6)
        actual_bar_len = int(actual_pct * 0.6)

        pred_bar = '█' * pred_bar_len
        actual_bar = '░' * actual_bar_len

        # Show both bars
        visualization = f"Pred: {pred_bar:<60} Act: {actual_bar:<60}"

        print(f"{f'{predicted_pct:.1f}%':<15} {f'{actual_pct:.1f}%':<15} {bin_name:<90}")

    # Interpretation Guide
    print(f"\n{'INTERPRETATION GUIDE':^120}")
    print("="*120)
    print("A well-calibrated model has:")
    print("  • Brier Score < 0.25 (lower is better; random guess = 0.25)")
    print("  • Calibration curve close to diagonal (predicted ≈ actual)")
    print("  • Small calibration errors (< 5% is excellent)")
    print("  • R² > 0.95 (predictions explain >95% of variance)")
    print()
    print("Current Model Assessment:")

    # Overall assessment
    if brier < 0.20 and mae < 5 and r_squared > 0.95:
        assessment = "✅ EXCELLENT - Model is very well calibrated!"
    elif brier < 0.25 and mae < 10 and r_squared > 0.90:
        assessment = "✓ GOOD - Model is reasonably well calibrated"
    elif brier < 0.30 and mae < 15:
        assessment = "~ FAIR - Model shows acceptable calibration"
    else:
        assessment = "⚠ NEEDS IMPROVEMENT - Consider adjusting K-factor or ELO formula"

    print(f"  {assessment}")
    print("="*120 + "\n")

if __name__ == "__main__":
    show_calibration()
