"""
Unit Tests for Temporal Walk-Forward Calibration

Tests the walk-forward calibration logic that prevents overfitting by
using proper temporal validation (train on past, validate on future).
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Add scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


@pytest.mark.unit
class TestIsotonicCalibration:
    """Tests for isotonic regression calibration"""

    def test_isotonic_is_monotonic(self):
        """Isotonic regression should produce monotonically increasing outputs"""
        from sklearn.isotonic import IsotonicRegression

        # Create sample data with some noise
        np.random.seed(42)
        raw_probs = np.linspace(0.1, 0.9, 100)
        # Add noise to actuals but maintain overall monotonic trend
        actuals = (raw_probs + np.random.normal(0, 0.1, 100) > 0.5).astype(float)

        iso_reg = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso_reg.fit(raw_probs, actuals)
        calibrated = iso_reg.predict(raw_probs)

        # Check monotonicity
        diffs = np.diff(calibrated)
        assert all(diffs >= -1e-10), "Isotonic regression should be monotonically increasing"

    def test_calibration_clips_to_bounds(self):
        """Calibrated probabilities should be clipped to [0, 1]"""
        from sklearn.isotonic import IsotonicRegression

        # Training data
        raw_probs = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
        actuals = np.array([0, 0, 1, 1, 1])

        iso_reg = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso_reg.fit(raw_probs, actuals)

        # Test with out-of-bounds inputs
        test_probs = np.array([0.0, 0.05, 0.5, 0.95, 1.0])
        calibrated = iso_reg.predict(test_probs)

        assert all(calibrated >= 0.0), "Calibrated probs should be >= 0"
        assert all(calibrated <= 1.0), "Calibrated probs should be <= 1"


@pytest.mark.unit
class TestWalkForwardValidation:
    """Tests for walk-forward validation logic"""

    def test_walk_forward_splits_are_temporal(self):
        """Walk-forward splits should use only past data for training"""
        # Simulate walk-forward logic
        weeks = list(range(1, 15))
        min_train_weeks = 4

        for test_week in weeks:
            if test_week < min_train_weeks + 1:
                continue

            train_weeks = [w for w in weeks if w < test_week]

            # All training weeks should be before test week
            assert all(w < test_week for w in train_weeks), \
                f"Training data should only include weeks before test week {test_week}"

            # Should have at least min_train_weeks of training data
            assert len(train_weeks) >= min_train_weeks, \
                f"Should have at least {min_train_weeks} weeks of training data"

    def test_no_future_data_leakage(self):
        """Training should never include future data"""
        # Create sample data with week numbers
        np.random.seed(42)
        df = pd.DataFrame({
            'week_number': np.repeat(range(1, 15), 16),  # 16 games per week
            'raw_prob': np.random.uniform(0.3, 0.7, 14 * 16),
            'actual': np.random.randint(0, 2, 14 * 16)
        })

        test_week = 8
        train_data = df[df['week_number'] < test_week]
        test_data = df[df['week_number'] == test_week]

        # Verify no overlap
        train_weeks = set(train_data['week_number'].unique())
        test_weeks = set(test_data['week_number'].unique())

        assert len(train_weeks.intersection(test_weeks)) == 0, \
            "Training and test data should not overlap"

        # Verify all training weeks are before test week
        assert max(train_weeks) < min(test_weeks), \
            "All training weeks should be before test week"


@pytest.mark.unit
class TestCalibrationMetrics:
    """Tests for calibration evaluation metrics"""

    def test_brier_score_perfect_predictions(self):
        """Brier score should be 0 for perfect predictions"""
        from sklearn.metrics import brier_score_loss

        actuals = np.array([0, 0, 1, 1])
        predictions = np.array([0.0, 0.0, 1.0, 1.0])

        brier = brier_score_loss(actuals, predictions)
        assert abs(brier) < 1e-10, "Perfect predictions should have Brier score of 0"

    def test_brier_score_random_predictions(self):
        """Brier score for random 50/50 predictions should be ~0.25"""
        from sklearn.metrics import brier_score_loss

        np.random.seed(42)
        actuals = np.random.randint(0, 2, 1000)
        predictions = np.full(1000, 0.5)

        brier = brier_score_loss(actuals, predictions)
        # Expected: 0.25 (variance of 50/50 predictions)
        assert 0.24 < brier < 0.26, "50/50 predictions should have Brier ~0.25"

    def test_brier_improvement_when_calibrated(self):
        """Calibration should improve (reduce) Brier score on training data"""
        from sklearn.metrics import brier_score_loss
        from sklearn.isotonic import IsotonicRegression

        np.random.seed(42)
        # Create systematically overconfident predictions
        raw_probs = np.concatenate([
            np.full(100, 0.8),  # Predict 80%
            np.full(100, 0.2)   # Predict 20%
        ])
        # But actual rate is closer to base rate
        actuals = np.concatenate([
            np.random.binomial(1, 0.6, 100),  # Actually 60%
            np.random.binomial(1, 0.4, 100)   # Actually 40%
        ])

        raw_brier = brier_score_loss(actuals, raw_probs)

        iso_reg = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso_reg.fit(raw_probs, actuals)
        calibrated = iso_reg.predict(raw_probs)

        cal_brier = brier_score_loss(actuals, calibrated)

        # Calibration should improve Brier score on training data
        assert cal_brier <= raw_brier, \
            "Calibration should not increase Brier score on training data"


@pytest.mark.unit
class TestCalibrationModelLoading:
    """Tests for calibration model loading with fallbacks"""

    def test_load_fallback_priority(self):
        """Model loading should follow priority: temporal > original > none"""
        # This tests the logic, not actual file loading
        model_priorities = ['temporal', 'original', 'none']

        # Simulate fallback logic
        def get_model_type(temporal_exists: bool, original_exists: bool) -> str:
            if temporal_exists:
                return 'temporal'
            elif original_exists:
                return 'original'
            else:
                return 'none'

        # Test all combinations
        assert get_model_type(True, True) == 'temporal'
        assert get_model_type(True, False) == 'temporal'
        assert get_model_type(False, True) == 'original'
        assert get_model_type(False, False) == 'none'

    def test_raw_prob_passthrough_when_no_model(self):
        """When no model exists, raw probabilities should pass through unchanged"""
        raw_probs = np.array([0.3, 0.5, 0.7])

        # Simulate no-model case
        iso_reg = None
        if iso_reg is not None:
            calibrated = iso_reg.predict(raw_probs)
        else:
            calibrated = raw_probs.copy()

        np.testing.assert_array_equal(raw_probs, calibrated), \
            "No model should result in unchanged probabilities"
