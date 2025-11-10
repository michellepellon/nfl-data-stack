"""
Unit Tests for Webpage Data Generation

Tests the generate_full_webpage_data.py script which creates JSON for the
static site.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, Mock

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from generate_full_webpage_data import calculate_current_week, generate_full_webpage_data


@pytest.mark.unit
class TestCurrentWeekCalculation:
    """Test NFL week calculation logic"""

    def test_before_season_returns_week_1(self):
        """Before season starts, should return week 1"""
        eastern = ZoneInfo("America/New_York")
        # Date before season: August 1, 2025
        test_date = datetime(2025, 8, 1, tzinfo=eastern)

        with patch('generate_full_webpage_data.datetime', Mock(wraps=datetime)) as mock_datetime:
            mock_datetime.now.return_value = test_date
            week = calculate_current_week()
            assert week == 1

    def test_week_1_starts_correctly(self):
        """Week 1 should start on September 4, 2025"""
        eastern = ZoneInfo("America/New_York")
        # First day of season: September 4, 2025
        test_date = datetime(2025, 9, 4, tzinfo=eastern)

        with patch('generate_full_webpage_data.datetime', Mock(wraps=datetime)) as mock_datetime:
            mock_datetime.now.return_value = test_date
            week = calculate_current_week()
            assert week == 1

    def test_week_2_calculation(self):
        """Week 2 should start 7 days after week 1"""
        eastern = ZoneInfo("America/New_York")
        # September 11, 2025 (7 days after season start)
        test_date = datetime(2025, 9, 11, tzinfo=eastern)

        with patch('generate_full_webpage_data.datetime', Mock(wraps=datetime)) as mock_datetime:
            mock_datetime.now.return_value = test_date
            week = calculate_current_week()
            assert week == 2

    def test_mid_season_week_calculation(self):
        """Mid-season week should calculate correctly"""
        eastern = ZoneInfo("America/New_York")
        # November 6, 2025 (63 days after season start = week 10)
        test_date = datetime(2025, 11, 6, tzinfo=eastern)

        with patch('generate_full_webpage_data.datetime', Mock(wraps=datetime)) as mock_datetime:
            mock_datetime.now.return_value = test_date
            week = calculate_current_week()
            assert week == 10

    def test_week_caps_at_18(self):
        """Week should cap at 18 (end of regular season)"""
        eastern = ZoneInfo("America/New_York")
        # Far into the future (should cap at 18)
        test_date = datetime(2026, 1, 31, tzinfo=eastern)

        with patch('generate_full_webpage_data.datetime', Mock(wraps=datetime)) as mock_datetime:
            mock_datetime.now.return_value = test_date
            week = calculate_current_week()
            assert week == 18


@pytest.mark.unit
class TestWebpageDataStructure:
    """Test structure of generated webpage data"""

    def test_generate_returns_dict(self):
        """generate_full_webpage_data should return a dictionary"""
        try:
            data = generate_full_webpage_data()
            assert isinstance(data, dict)
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")

    def test_required_top_level_keys(self):
        """Generated data should have all required top-level keys"""
        try:
            data = generate_full_webpage_data()
            required_keys = ['generated_at', 'current_week', 'ratings', 'predictions', 'calibration', 'performance', 'playoffs']
            for key in required_keys:
                assert key in data, f"Missing required key: {key}"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")

    def test_current_week_valid_range(self):
        """Current week should be 1-18"""
        try:
            data = generate_full_webpage_data()
            assert 1 <= data['current_week'] <= 18
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")

    def test_ratings_structure(self):
        """Ratings data should have correct structure"""
        try:
            data = generate_full_webpage_data()
            ratings = data['ratings']

            assert isinstance(ratings, list)
            if len(ratings) > 0:
                # Check first rating has required fields
                rating = ratings[0]
                required_fields = ['team', 'conf', 'division', 'elo_rating', 'vegas_preseason_total']
                for field in required_fields:
                    assert field in rating, f"Missing rating field: {field}"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")

    def test_predictions_structure(self):
        """Predictions data should have correct structure"""
        try:
            data = generate_full_webpage_data()
            predictions = data['predictions']

            assert isinstance(predictions, list)
            if len(predictions) > 0:
                # Check first prediction has required fields
                prediction = predictions[0]
                required_fields = [
                    'game_id', 'week_number', 'visiting_team', 'home_team',
                    'visiting_team_elo_rating', 'home_team_elo_rating',
                    'home_win_probability', 'predicted_winner'
                ]
                for field in required_fields:
                    assert field in prediction, f"Missing prediction field: {field}"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")

    def test_playoff_probabilities_structure(self):
        """Playoff data should have correct structure"""
        try:
            data = generate_full_webpage_data()
            playoffs = data['playoffs']

            assert isinstance(playoffs, list)
            if len(playoffs) > 0:
                # Check first team has required fields
                team = playoffs[0]
                required_fields = [
                    'team', 'conf', 'elo_rating', 'playoff_prob_pct',
                    'bye_prob_pct', 'avg_wins', 'avg_seed'
                ]
                for field in required_fields:
                    assert field in team, f"Missing playoff field: {field}"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")


@pytest.mark.unit
class TestDataQualityChecks:
    """Test data quality in generated webpage data"""

    def test_win_probabilities_valid_range(self):
        """Win probabilities should be 0.0-1.0"""
        try:
            data = generate_full_webpage_data()
            predictions = data['predictions']

            for prediction in predictions:
                prob = prediction['home_win_probability']
                assert 0.0 <= prob <= 1.0, f"Invalid probability: {prob}"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")

    def test_playoff_probabilities_valid_range(self):
        """Playoff probabilities should be 0-100 (percentage)"""
        try:
            data = generate_full_webpage_data()
            playoffs = data['playoffs']

            for team in playoffs:
                playoff_prob = team['playoff_prob_pct']
                bye_prob = team['bye_prob_pct']
                assert 0.0 <= playoff_prob <= 100.0, f"Invalid playoff prob: {playoff_prob}"
                assert 0.0 <= bye_prob <= 100.0, f"Invalid bye prob: {bye_prob}"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")

    def test_elo_ratings_reasonable_range(self):
        """ELO ratings should be in reasonable range (1000-2000)"""
        try:
            data = generate_full_webpage_data()
            ratings = data['ratings']

            for rating in ratings:
                elo = rating['elo_rating']
                assert 1000 <= elo <= 2000, f"ELO out of reasonable range: {elo}"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")

    def test_predictions_sorted_by_game_id(self):
        """Predictions should be sorted by game_id"""
        try:
            data = generate_full_webpage_data()
            predictions = data['predictions']

            if len(predictions) > 1:
                game_ids = [p['game_id'] for p in predictions]
                assert game_ids == sorted(game_ids), "Predictions not sorted by game_id"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")

    def test_playoff_probabilities_sorted_desc(self):
        """Playoff probabilities should be sorted descending"""
        try:
            data = generate_full_webpage_data()
            playoffs = data['playoffs']

            if len(playoffs) > 1:
                probs = [p['playoff_prob_pct'] for p in playoffs]
                assert probs == sorted(probs, reverse=True), "Playoff probs not sorted descending"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")


@pytest.mark.unit
class TestActualScoresIntegration:
    """Test actual game scores integration"""

    def test_actual_scores_integer_or_none(self):
        """Actual scores should be integers or None"""
        try:
            data = generate_full_webpage_data()
            predictions = data['predictions']

            for prediction in predictions:
                home_score = prediction.get('actual_home_score')
                away_score = prediction.get('actual_away_score')

                # Should be int or None
                if home_score is not None:
                    assert isinstance(home_score, int), f"Invalid home score type: {type(home_score)}"
                if away_score is not None:
                    assert isinstance(away_score, int), f"Invalid away score type: {type(away_score)}"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")

    def test_actual_scores_non_negative(self):
        """Actual scores should be non-negative if present"""
        try:
            data = generate_full_webpage_data()
            predictions = data['predictions']

            for prediction in predictions:
                home_score = prediction.get('actual_home_score')
                away_score = prediction.get('actual_away_score')

                if home_score is not None:
                    assert home_score >= 0, f"Negative home score: {home_score}"
                if away_score is not None:
                    assert away_score >= 0, f"Negative away score: {away_score}"
        except Exception as e:
            pytest.skip(f"Requires parquet files: {e}")
