"""
Backtest Week 11 predictions: Baseline ELO vs Momentum-Adjusted

Compares three prediction approaches:
1. Baseline: Pure ELO (home_win_prob_base)
2. Features: ELO + weather/rest adjustments (pre-momentum)
3. Momentum: ELO + features + recent form (home_win_prob_adjusted)

Calculates:
- Accuracy (% games predicted correctly)
- Brier Score (calibration quality)
- Log Loss (overall prediction quality)
- Prediction flips (games where momentum changed the prediction)
"""

import pandas as pd
import numpy as np


def calculate_metrics(predictions, actuals):
    """Calculate accuracy, Brier score, and log loss."""
    correct = (predictions == actuals).sum()
    accuracy = correct / len(predictions)

    # For probabilistic metrics, need probabilities not just predictions
    return {
        'accuracy': accuracy,
        'correct': correct,
        'total': len(predictions)
    }


def calculate_brier_score(prob_home_wins, actual_home_wins):
    """Brier score: mean squared error of probabilities."""
    return ((prob_home_wins - actual_home_wins) ** 2).mean()


def calculate_log_loss(prob_home_wins, actual_home_wins):
    """Log loss (cross-entropy): -mean(y*log(p) + (1-y)*log(1-p))."""
    epsilon = 1e-15
    prob_home_wins = np.clip(prob_home_wins, epsilon, 1 - epsilon)
    return -(actual_home_wins * np.log(prob_home_wins) +
             (1 - actual_home_wins) * np.log(1 - prob_home_wins)).mean()


def main():
    # Load predictions with features and momentum
    pred_df = pd.read_parquet('../data/data_catalog/nfl_predictions_with_features.parquet')

    # Load actual results
    results_df = pd.read_parquet('../data/data_catalog/nfl_latest_results.parquet')

    # Filter to Week 11
    week11_pred = pred_df[pred_df['week_number'] == 11].copy()
    week11_results = results_df[results_df['week_number'] == 11].copy()

    # Join predictions with results
    merged = week11_pred.merge(
        week11_results[['home_team', 'visiting_team', 'winning_team', 'home_team_score', 'visiting_team_score']],
        on=['home_team', 'visiting_team'],
        how='inner',
        suffixes=('', '_result')
    )

    print(f"=== Week 11 Backtest: Momentum Improvement Analysis ===\n")
    print(f"Total games with results: {len(merged)}\n")
    print(f"Merged columns: {list(merged.columns)}\n")

    # Calculate actual outcomes
    merged['actual_home_win'] = (merged['home_team_score'] > merged['visiting_team_score']).astype(int)

    # Use whichever winning_team column exists
    if 'winning_team' in merged.columns:
        merged['actual_winner'] = merged['winning_team']
    elif 'winning_team_result' in merged.columns:
        merged['actual_winner'] = merged['winning_team_result']
    else:
        # Calculate from scores
        merged['actual_winner'] = merged.apply(
            lambda row: row['home_team'] if row['home_team_score'] > row['visiting_team_score'] else row['visiting_team'],
            axis=1
        )

    # Baseline predictions (pure ELO)
    merged['pred_baseline'] = (merged['home_win_prob_base'] > 0.5).astype(int)
    merged['correct_baseline'] = (merged['pred_baseline'] == merged['actual_home_win']).astype(int)

    # Features predictions (ELO + weather/rest, pre-momentum)
    # Reconstruct pre-momentum probability
    merged['elo_diff_features'] = merged['elo_diff'] + merged['total_adj']
    merged['home_win_prob_features'] = 1.0 / (1.0 + 10 ** (-((merged['elo_diff_features'] + 52) / 400.0)))
    merged['pred_features'] = (merged['home_win_prob_features'] > 0.5).astype(int)
    merged['correct_features'] = (merged['pred_features'] == merged['actual_home_win']).astype(int)

    # Momentum predictions (ELO + features + momentum)
    merged['pred_momentum'] = (merged['home_win_prob_adjusted'] > 0.5).astype(int)
    merged['correct_momentum'] = (merged['pred_momentum'] == merged['actual_home_win']).astype(int)

    # Calculate metrics for each approach
    baseline_acc = merged['correct_baseline'].mean()
    baseline_brier = calculate_brier_score(merged['home_win_prob_base'], merged['actual_home_win'])
    baseline_logloss = calculate_log_loss(merged['home_win_prob_base'], merged['actual_home_win'])

    features_acc = merged['correct_features'].mean()
    features_brier = calculate_brier_score(merged['home_win_prob_features'], merged['actual_home_win'])
    features_logloss = calculate_log_loss(merged['home_win_prob_features'], merged['actual_home_win'])

    momentum_acc = merged['correct_momentum'].mean()
    momentum_brier = calculate_brier_score(merged['home_win_prob_adjusted'], merged['actual_home_win'])
    momentum_logloss = calculate_log_loss(merged['home_win_prob_adjusted'], merged['actual_home_win'])

    # Print comparison table
    print("=== Performance Comparison ===\n")
    print(f"{'Metric':<20} {'Baseline':<15} {'Features':<15} {'Momentum':<15} {'Improvement':<15}")
    print("-" * 80)
    print(f"{'Accuracy':<20} {baseline_acc:<15.1%} {features_acc:<15.1%} {momentum_acc:<15.1%} {(momentum_acc - baseline_acc)*100:+.1f} pp")
    print(f"{'Brier Score':<20} {baseline_brier:<15.4f} {features_brier:<15.4f} {momentum_brier:<15.4f} {(baseline_brier - momentum_brier)/baseline_brier:+.1%}")
    print(f"{'Log Loss':<20} {baseline_logloss:<15.4f} {features_logloss:<15.4f} {momentum_logloss:<15.4f} {(baseline_logloss - momentum_logloss)/baseline_logloss:+.1%}")

    # Find games where momentum changed the prediction
    merged['baseline_to_momentum_flip'] = (merged['pred_baseline'] != merged['pred_momentum']).astype(int)
    merged['features_to_momentum_flip'] = (merged['pred_features'] != merged['pred_momentum']).astype(int)

    flips_baseline = merged[merged['baseline_to_momentum_flip'] == 1].copy()
    flips_features = merged[merged['features_to_momentum_flip'] == 1].copy()

    print(f"\n=== Prediction Flips ===\n")
    print(f"Baseline → Momentum flips: {len(flips_baseline)} games")
    print(f"Features → Momentum flips: {len(flips_features)} games")

    if len(flips_baseline) > 0:
        print(f"\n=== Games where momentum changed prediction from baseline ===\n")
        for _, game in flips_baseline.iterrows():
            baseline_pred = game['home_team'] if game['pred_baseline'] == 1 else game['visiting_team']
            momentum_pred = game['home_team'] if game['pred_momentum'] == 1 else game['visiting_team']
            winner = game['actual_winner']
            momentum_correct = '✓' if momentum_pred == winner else '✗'

            home_momentum = game.get('home_momentum_adj', 0)
            away_momentum = game.get('away_momentum_adj', 0)

            print(f"{game['visiting_team']} @ {game['home_team']}")
            print(f"  Baseline predicted: {baseline_pred}")
            print(f"  Momentum predicted: {momentum_pred} {momentum_correct}")
            print(f"  Actual winner: {winner}")
            print(f"  Home momentum: {home_momentum:+.1f}, Away momentum: {away_momentum:+.1f}")
            print(f"  Score: {game['visiting_team']} {game['visiting_team_score']}, {game['home_team']} {game['home_team_score']}")
            print()

    # Identify the 5 biggest errors in baseline that momentum would have fixed
    merged['baseline_error'] = abs(merged['home_win_prob_base'] - merged['actual_home_win'])
    merged['momentum_improvement'] = merged['baseline_error'] - abs(merged['home_win_prob_adjusted'] - merged['actual_home_win'])

    biggest_improvements = merged.nlargest(5, 'momentum_improvement')

    print(f"\n=== Top 5 games where momentum most improved predictions ===\n")
    for _, game in biggest_improvements.iterrows():
        baseline_prob = game['home_win_prob_base']
        momentum_prob = game['home_win_prob_adjusted']
        home_win = game['actual_home_win']

        baseline_pred = game['home_team'] if baseline_prob > 0.5 else game['visiting_team']
        momentum_pred = game['home_team'] if momentum_prob > 0.5 else game['visiting_team']
        winner = game['actual_winner']

        baseline_correct = '✓' if baseline_pred == winner else '✗'
        momentum_correct = '✓' if momentum_pred == winner else '✗'

        print(f"{game['visiting_team']} @ {game['home_team']}")
        print(f"  Baseline: {baseline_pred} ({baseline_prob:.1%}) {baseline_correct}")
        print(f"  Momentum: {momentum_pred} ({momentum_prob:.1%}) {momentum_correct}")
        print(f"  Actual: {winner}")
        print(f"  Error reduction: {game['momentum_improvement']:.3f}")
        print(f"  Score: {game['visiting_team']} {game['visiting_team_score']}, {game['home_team']} {game['home_team_score']}")
        print()


if __name__ == '__main__':
    main()
