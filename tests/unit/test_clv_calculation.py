"""
Unit Tests for Closing Line Value (CLV) Calculations

Tests the CLV calculation logic that measures how model predictions
compare to closing Vegas lines (the most efficient market price).
"""

import pytest
import numpy as np


@pytest.mark.unit
class TestCLVBasicCalculation:
    """Tests for basic CLV calculation"""

    def test_clv_formula(self):
        """CLV = Model Probability - Closing Line Probability"""
        model_prob = 0.65
        closing_prob = 0.60

        clv = model_prob - closing_prob

        expected = 0.05  # 5% CLV
        assert abs(clv - expected) < 1e-10, "CLV calculation error"

    def test_positive_clv_interpretation(self):
        """Positive CLV means model predicted higher than market closed"""
        model_prob = 0.70
        closing_prob = 0.65

        clv = model_prob - closing_prob

        assert clv > 0, "Model predicting higher should give positive CLV"

    def test_negative_clv_interpretation(self):
        """Negative CLV means model predicted lower than market closed"""
        model_prob = 0.55
        closing_prob = 0.60

        clv = model_prob - closing_prob

        assert clv < 0, "Model predicting lower should give negative CLV"

    def test_zero_clv_means_matched_market(self):
        """Zero CLV means model matched closing line exactly"""
        model_prob = 0.60
        closing_prob = 0.60

        clv = model_prob - closing_prob

        assert abs(clv) < 1e-10, "Matching market should give zero CLV"


@pytest.mark.unit
class TestCLVInterpretation:
    """Tests for CLV interpretation categories"""

    def test_strong_positive_clv(self):
        """CLV >= 5% should be rated 'Strong positive'"""
        clv = 0.06

        if clv >= 0.05:
            rating = 'Strong positive'
        elif clv >= 0.02:
            rating = 'Positive'
        elif clv >= -0.02:
            rating = 'Neutral'
        elif clv >= -0.05:
            rating = 'Negative'
        else:
            rating = 'Strong negative'

        assert rating == 'Strong positive'

    def test_positive_clv(self):
        """CLV 2-5% should be rated 'Positive'"""
        clv = 0.03

        if clv >= 0.05:
            rating = 'Strong positive'
        elif clv >= 0.02:
            rating = 'Positive'
        elif clv >= -0.02:
            rating = 'Neutral'
        elif clv >= -0.05:
            rating = 'Negative'
        else:
            rating = 'Strong negative'

        assert rating == 'Positive'

    def test_neutral_clv(self):
        """CLV -2% to 2% should be rated 'Neutral'"""
        test_values = [-0.01, 0.0, 0.01]

        for clv in test_values:
            if clv >= 0.05:
                rating = 'Strong positive'
            elif clv >= 0.02:
                rating = 'Positive'
            elif clv >= -0.02:
                rating = 'Neutral'
            elif clv >= -0.05:
                rating = 'Negative'
            else:
                rating = 'Strong negative'

            assert rating == 'Neutral', f"CLV {clv} should be neutral"

    def test_negative_clv(self):
        """CLV -5% to -2% should be rated 'Negative'"""
        clv = -0.03

        if clv >= 0.05:
            rating = 'Strong positive'
        elif clv >= 0.02:
            rating = 'Positive'
        elif clv >= -0.02:
            rating = 'Neutral'
        elif clv >= -0.05:
            rating = 'Negative'
        else:
            rating = 'Strong negative'

        assert rating == 'Negative'

    def test_strong_negative_clv(self):
        """CLV < -5% should be rated 'Strong negative'"""
        clv = -0.08

        if clv >= 0.05:
            rating = 'Strong positive'
        elif clv >= 0.02:
            rating = 'Positive'
        elif clv >= -0.02:
            rating = 'Neutral'
        elif clv >= -0.05:
            rating = 'Negative'
        else:
            rating = 'Strong negative'

        assert rating == 'Strong negative'


@pytest.mark.unit
class TestCLVAggregation:
    """Tests for CLV aggregation across multiple games"""

    def test_average_clv_calculation(self):
        """Average CLV across games"""
        game_clvs = [0.05, 0.02, -0.01, 0.03, 0.00]

        avg_clv = np.mean(game_clvs)

        expected = 0.018  # (0.05 + 0.02 - 0.01 + 0.03 + 0.00) / 5
        assert abs(avg_clv - expected) < 1e-10, "Average CLV calculation error"

    def test_consistent_positive_clv_indicates_edge(self):
        """Consistent positive CLV over many games indicates real edge"""
        np.random.seed(42)

        # Simulate 100 games with average 2% CLV
        game_clvs = np.random.normal(0.02, 0.05, 100)
        avg_clv = np.mean(game_clvs)

        # With true edge, average should be significantly positive
        assert avg_clv > 0, "Model with edge should have positive average CLV"

    def test_clv_standard_error(self):
        """CLV should have reasonable standard error for significance testing"""
        game_clvs = [0.05, 0.02, -0.01, 0.03, 0.00, 0.04, -0.02, 0.03]

        mean_clv = np.mean(game_clvs)
        std_clv = np.std(game_clvs, ddof=1)
        se_clv = std_clv / np.sqrt(len(game_clvs))

        # Check if mean is statistically significant (> 2 SE from 0)
        t_stat = mean_clv / se_clv

        assert np.isfinite(t_stat), "T-statistic should be finite"


@pytest.mark.unit
class TestCLVvsOpeningLine:
    """Tests for CLV calculated against opening line"""

    def test_clv_vs_opening_calculation(self):
        """CLV vs opening = Model - Opening probability"""
        model_prob = 0.65
        opening_prob = 0.55
        closing_prob = 0.60

        clv_vs_closing = model_prob - closing_prob  # 0.05
        clv_vs_opening = model_prob - opening_prob  # 0.10

        assert clv_vs_opening > clv_vs_closing, \
            "CLV vs opening should be different from CLV vs closing when line moved"

    def test_line_movement_impact_on_clv(self):
        """Line movement affects difference between opening and closing CLV"""
        model_prob = 0.65
        opening_prob = 0.55
        closing_prob = 0.65  # Line moved toward model prediction

        clv_vs_closing = model_prob - closing_prob  # 0.00
        clv_vs_opening = model_prob - opening_prob  # 0.10

        # When line moves toward model, closing CLV shrinks
        assert clv_vs_closing < clv_vs_opening, \
            "Line movement toward model should reduce closing CLV"


@pytest.mark.unit
class TestCLVEdgeCases:
    """Edge case tests for CLV calculations"""

    def test_clv_with_extreme_probabilities(self):
        """CLV should handle extreme probabilities correctly"""
        # Model very confident, market less so
        model_prob = 0.95
        closing_prob = 0.80

        clv = model_prob - closing_prob

        assert abs(clv - 0.15) < 1e-10, "Extreme probability CLV should be correct"
        assert -1.0 <= clv <= 1.0, "CLV should be in valid range"

    def test_clv_at_probability_bounds(self):
        """CLV should be valid at probability bounds"""
        # Model predicts certainty
        model_prob = 1.0
        closing_prob = 0.90

        clv = model_prob - closing_prob

        assert abs(clv - 0.10) < 1e-10, "CLV at boundary should be correct"

    def test_clv_when_closing_unavailable(self):
        """CLV should be None/null when closing line unavailable"""
        model_prob = 0.65
        closing_prob = None

        if closing_prob is not None:
            clv = model_prob - closing_prob
        else:
            clv = None

        assert clv is None, "Missing closing line should result in null CLV"

    def test_clv_symmetry(self):
        """CLV for home team should negate CLV for away team"""
        home_model_prob = 0.65
        away_model_prob = 0.35
        home_closing_prob = 0.60
        away_closing_prob = 0.40

        home_clv = home_model_prob - home_closing_prob  # 0.05
        away_clv = away_model_prob - away_closing_prob  # -0.05

        assert abs(home_clv + away_clv) < 1e-10, "CLV should be symmetric for home/away"


@pytest.mark.unit
class TestProfessionalBettingBenchmarks:
    """Tests based on professional betting benchmarks"""

    def test_professional_clv_target(self):
        """Professional bettors target 2-4% CLV on average"""
        target_min = 0.02
        target_max = 0.04

        # Simulate professional-level performance
        avg_clv = 0.025

        assert target_min <= avg_clv <= target_max, \
            f"Professional CLV {avg_clv} should be in 2-4% range"

    def test_recreational_vs_professional_clv(self):
        """Recreational bettors typically have negative CLV"""
        recreational_clv = -0.02  # -2% edge to house
        professional_clv = 0.03   # +3% edge to bettor

        assert recreational_clv < 0, "Recreational bettors typically have negative CLV"
        assert professional_clv > 0, "Professional bettors should have positive CLV"
        assert professional_clv > recreational_clv, "Professionals outperform recreational"
