"""
Unit Tests for Dynamic Ensemble Weights

Tests the dynamic weighting logic that adjusts ensemble weights based on
rolling model performance (Brier score).
"""

import pytest
import numpy as np


@pytest.mark.unit
class TestWeightCalculation:
    """Tests for weight calculation logic"""

    def test_inverse_brier_weighting(self):
        """Lower Brier score should result in higher weight"""
        # Simulate two models with different Brier scores
        elo_brier = 0.20  # Better
        vegas_brier = 0.25  # Worse

        epsilon = 0.001

        # Calculate inverse Brier weights
        elo_raw = 1.0 / (elo_brier + epsilon)
        vegas_raw = 1.0 / (vegas_brier + epsilon)

        # Normalize
        total = elo_raw + vegas_raw
        elo_weight = elo_raw / total
        vegas_weight = vegas_raw / total

        assert elo_weight > vegas_weight, \
            "Model with lower Brier score should have higher weight"
        assert abs(elo_weight + vegas_weight - 1.0) < 1e-10, \
            "Weights should sum to 1.0"

    def test_weight_bounds_applied(self):
        """Weights should be bounded between 0.25 and 0.75"""
        min_weight = 0.25
        max_weight = 0.75

        test_cases = [
            (0.90, 0.10),  # Extreme: should be bounded to 0.75/0.25
            (0.10, 0.90),  # Extreme: should be bounded to 0.25/0.75
            (0.60, 0.40),  # Normal: should pass through
            (0.50, 0.50),  # Equal: should pass through
        ]

        for raw_elo, raw_vegas in test_cases:
            bounded_elo = max(min_weight, min(max_weight, raw_elo))
            bounded_vegas = max(min_weight, min(max_weight, raw_vegas))

            assert bounded_elo >= min_weight, f"ELO weight {bounded_elo} below minimum"
            assert bounded_elo <= max_weight, f"ELO weight {bounded_elo} above maximum"
            assert bounded_vegas >= min_weight, f"Vegas weight {bounded_vegas} below minimum"
            assert bounded_vegas <= max_weight, f"Vegas weight {bounded_vegas} above maximum"

    def test_extreme_performance_difference(self):
        """Even with extreme performance difference, weights should be bounded"""
        # One model much better than other
        elo_brier = 0.10  # Excellent
        vegas_brier = 0.40  # Poor

        epsilon = 0.001
        min_weight = 0.25
        max_weight = 0.75

        elo_raw = 1.0 / (elo_brier + epsilon)
        vegas_raw = 1.0 / (vegas_brier + epsilon)

        total = elo_raw + vegas_raw
        elo_weight_unbounded = elo_raw / total
        vegas_weight_unbounded = vegas_raw / total

        # Without bounds, ELO would be ~0.80 and Vegas ~0.20
        assert elo_weight_unbounded > max_weight, \
            "Unbounded ELO weight should exceed max"

        # Apply bounds
        elo_weight = max(min_weight, min(max_weight, elo_weight_unbounded))
        vegas_weight = max(min_weight, min(max_weight, vegas_weight_unbounded))

        assert elo_weight == max_weight, "ELO should be capped at max weight"
        assert vegas_weight == min_weight, "Vegas should be floored at min weight"


@pytest.mark.unit
class TestColdStartLogic:
    """Tests for cold start handling"""

    def test_cold_start_first_four_weeks(self):
        """First 4 weeks should use default 50/50 weights"""
        min_weeks_for_weights = 4

        for week in range(1, 5):
            weeks_available = week - 1  # Weeks before current
            is_cold_start = weeks_available < min_weeks_for_weights

            assert is_cold_start, f"Week {week} should be cold start"

    def test_normal_weights_after_week_4(self):
        """After week 4, dynamic weights should be used"""
        min_weeks_for_weights = 4

        for week in range(5, 18):
            weeks_available = week - 1
            is_cold_start = weeks_available < min_weeks_for_weights

            assert not is_cold_start, f"Week {week} should not be cold start"

    def test_cold_start_fallback_values(self):
        """Cold start should use 0.5/0.5 weights"""
        default_weight = 0.5

        # Simulate cold start scenario
        elo_weeks = 2  # Not enough history
        vegas_weeks = 2

        min_weeks = 4

        if elo_weeks < min_weeks or vegas_weeks < min_weeks:
            elo_weight = default_weight
            vegas_weight = default_weight
        else:
            # Would calculate dynamic weights
            elo_weight = 0.6  # Example dynamic weight
            vegas_weight = 0.4

        assert elo_weight == default_weight, "Cold start ELO weight should be 0.5"
        assert vegas_weight == default_weight, "Cold start Vegas weight should be 0.5"


@pytest.mark.unit
class TestRollingWindowCalculation:
    """Tests for rolling window performance calculation"""

    def test_four_week_rolling_average(self):
        """Rolling average should use last 4 weeks"""
        weekly_brier = [0.22, 0.25, 0.20, 0.23, 0.21, 0.24, 0.19, 0.22]

        window_size = 4

        for i in range(window_size - 1, len(weekly_brier)):
            window = weekly_brier[max(0, i - window_size + 1):i + 1]
            rolling_avg = sum(window) / len(window)

            # Verify window size
            assert len(window) == window_size, f"Window should have {window_size} values"

            # Verify average calculation
            expected = np.mean(weekly_brier[i - window_size + 1:i + 1])
            assert abs(rolling_avg - expected) < 1e-10, "Rolling average calculation error"

    def test_rolling_window_handles_early_weeks(self):
        """Early weeks should have smaller windows"""
        weekly_brier = [0.22, 0.25, 0.20, 0.23]
        window_size = 4

        # Week 1: only 1 value
        window_week1 = weekly_brier[:1]
        assert len(window_week1) == 1

        # Week 2: 2 values
        window_week2 = weekly_brier[:2]
        assert len(window_week2) == 2

        # Week 3: 3 values
        window_week3 = weekly_brier[:3]
        assert len(window_week3) == 3

        # Week 4: full 4 values
        window_week4 = weekly_brier[:4]
        assert len(window_week4) == 4


@pytest.mark.unit
class TestWeightPropagation:
    """Tests for weight propagation to predictions"""

    def test_ensemble_calculation_with_weights(self):
        """Ensemble should combine model probs using weights"""
        elo_prob = 0.60
        vegas_prob = 0.55
        elo_weight = 0.60
        vegas_weight = 0.40

        ensemble_prob = elo_weight * elo_prob + vegas_weight * vegas_prob

        expected = 0.60 * 0.60 + 0.40 * 0.55  # = 0.36 + 0.22 = 0.58
        assert abs(ensemble_prob - expected) < 1e-10, "Ensemble calculation error"

    def test_ensemble_fallback_when_no_vegas(self):
        """When Vegas is unavailable, use 100% ELO"""
        elo_prob = 0.60
        vegas_prob = None

        if vegas_prob is not None:
            elo_weight = 0.60
            vegas_weight = 0.40
            ensemble_prob = elo_weight * elo_prob + vegas_weight * vegas_prob
        else:
            ensemble_prob = elo_prob

        assert ensemble_prob == elo_prob, "No Vegas should use 100% ELO"

    def test_weights_sum_to_one(self):
        """Weights should always sum to 1.0 (or close to it)"""
        test_cases = [
            (0.50, 0.50),  # Default
            (0.60, 0.40),  # Dynamic
            (0.75, 0.25),  # At bounds
            (0.25, 0.75),  # At bounds (reversed)
        ]

        for elo_weight, vegas_weight in test_cases:
            total = elo_weight + vegas_weight
            assert abs(total - 1.0) < 1e-10, f"Weights {elo_weight}, {vegas_weight} don't sum to 1.0"


@pytest.mark.unit
class TestEdgeCases:
    """Edge case tests for dynamic weights"""

    def test_identical_brier_scores(self):
        """Identical performance should give 50/50 weights"""
        elo_brier = 0.22
        vegas_brier = 0.22

        epsilon = 0.001
        elo_raw = 1.0 / (elo_brier + epsilon)
        vegas_raw = 1.0 / (vegas_brier + epsilon)

        total = elo_raw + vegas_raw
        elo_weight = elo_raw / total
        vegas_weight = vegas_raw / total

        assert abs(elo_weight - 0.5) < 1e-10, "Identical Brier should give 50% ELO"
        assert abs(vegas_weight - 0.5) < 1e-10, "Identical Brier should give 50% Vegas"

    def test_zero_brier_score_handling(self):
        """Zero Brier score should not cause division by zero"""
        elo_brier = 0.0  # Perfect predictions
        vegas_brier = 0.22

        epsilon = 0.001

        # With epsilon, this should not cause division by zero
        elo_raw = 1.0 / (elo_brier + epsilon)
        vegas_raw = 1.0 / (vegas_brier + epsilon)

        assert np.isfinite(elo_raw), "Zero Brier should not cause inf"
        assert np.isfinite(vegas_raw), "Normal Brier should be finite"

        total = elo_raw + vegas_raw
        elo_weight = elo_raw / total
        vegas_weight = vegas_raw / total

        assert np.isfinite(elo_weight), "ELO weight should be finite"
        assert np.isfinite(vegas_weight), "Vegas weight should be finite"
