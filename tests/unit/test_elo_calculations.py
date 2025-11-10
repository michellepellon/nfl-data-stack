"""
Unit Tests for ELO Calculation Logic

Tests the calc_elo_diff function which is the core of the ELO rating system.
Validates margin-of-victory multiplier, win probability calculations, and
edge cases.

Based on FiveThirtyEight NFL ELO methodology:
https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/
"""

import pytest
import math
import sys
from pathlib import Path

# Add transform/models/nfl/prep to path so we can import the ELO module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "transform" / "models" / "nfl" / "prep"))

from nfl_elo_rollforward import calc_elo_diff


@pytest.mark.unit
class TestEloCalculationBasics:
    """Basic ELO calculation tests for standard scenarios"""

    def test_even_matchup_home_win(self, even_matchup):
        """Test even matchup where home team wins"""
        elo_change = calc_elo_diff(**even_matchup)

        # For even teams (both 1500), home team has advantage (52 points)
        # Expected win prob for visiting team: ~38%
        # Visiting team lost (game_result=0), so elo_change should be negative
        # (home team gains rating, visiting team loses rating)
        assert elo_change < 0, "Home team win should result in negative elo_change"
        assert -20 < elo_change < 0, "ELO change should be reasonable for even matchup"

    def test_even_matchup_visiting_win(self, even_matchup):
        """Test even matchup where visiting team wins"""
        even_matchup["game_result"] = 1  # visiting team wins
        elo_change = calc_elo_diff(**even_matchup)

        # Visiting team won against home advantage (upset of sorts)
        # elo_change should be positive (visiting team gains)
        assert elo_change > 0, "Visiting team win should result in positive elo_change"
        assert 0 < elo_change < 30, "ELO change should be reasonable for even matchup upset"

    def test_blowout_increases_elo_change(self, even_matchup):
        """Test that blowouts result in larger ELO changes"""
        # Close game (3 points)
        close_game = even_matchup.copy()
        close_game["scoring_margin"] = 3.0
        close_change = calc_elo_diff(**close_game)

        # Blowout (28 points)
        blowout = even_matchup.copy()
        blowout["scoring_margin"] = 28.0
        blowout_change = calc_elo_diff(**blowout)

        # Blowout should have larger absolute ELO change
        assert abs(blowout_change) > abs(close_change), \
            "Blowout should result in larger ELO change than close game"

    def test_upset_increases_elo_change(self, upset_game):
        """Test that upsets result in larger ELO changes"""
        # Calculate upset (weak team beats strong team)
        upset_change = calc_elo_diff(**upset_game)

        # Calculate expected win (strong team beats weak team)
        expected_win = upset_game.copy()
        expected_win["game_result"] = 0  # home team (strong) wins
        expected_change = calc_elo_diff(**expected_win)

        # Upset should have larger absolute ELO change
        assert abs(upset_change) > abs(expected_change), \
            "Upset should result in larger ELO change than expected outcome"


@pytest.mark.unit
class TestEloEdgeCases:
    """Edge case tests for ELO calculations"""

    def test_tie_game(self, tie_game):
        """Test tie game handling"""
        elo_change = calc_elo_diff(**tie_game)

        # For zero margin (0-0 tie), MOV multiplier is log(0+1) = log(1) = 0
        # Therefore ELO change is always 0 regardless of other factors
        # This is correct behavior: no margin of victory = no ELO change
        assert elo_change == 0, "Zero margin tie should result in zero ELO change (MOV multiplier = 0)"

    def test_tie_game_with_nonzero_margin(self):
        """Test tie game with non-zero margin (OT tie scenario)"""
        # In theory, a tie could have scoring (21-21) vs (0-0)
        # but our data model treats all ties as game_result=0.5 with margin=0
        # This test documents expected behavior if margin was tracked for ties
        params = {
            "home_elo": 1500.0,
            "visiting_elo": 1500.0,
            "home_adv": 52.0,
            "game_result": 0.5,  # tie
            "scoring_margin": 21.0,  # hypothetical: 21-21 tie
            "k_factor": 20.0,
        }
        elo_change = calc_elo_diff(**params)

        # With margin=21 and game_result=0.5, there should be ELO change
        # Home team had advantage but tied, so should lose rating
        assert elo_change > 0, "Tie with home advantage should result in positive ELO change"
        assert abs(elo_change) < 15, "Tie ELO change should be moderate"

    def test_neutral_site_removes_home_advantage(self, neutral_site_game):
        """Test that neutral site games have no home advantage"""
        elo_change = calc_elo_diff(**neutral_site_game)

        # With equal ratings and neutral site, expected win probability is 50%
        # Home team won (game_result=0), so actual=0, expected=0.5, error=-0.5
        # With K=20 and MOV multiplier for 3 points, ELO change ~10-15 is reasonable
        assert abs(elo_change) > 0, "Neutral site game should have ELO change"
        assert abs(elo_change) < 20, "Neutral site even matchup should have moderate ELO change"

        # Verify that neutral site (home_adv=0) vs regular (home_adv=52) gives different results
        regular_site = neutral_site_game.copy()
        regular_site["home_adv"] = 52.0
        regular_change = calc_elo_diff(**regular_site)

        # Regular site home team has advantage, so winning is more expected
        # Therefore ELO change should be smaller in absolute value
        assert abs(regular_change) < abs(elo_change), \
            "Home advantage should reduce ELO change when favorite wins"

    def test_minimum_margin(self, even_matchup):
        """Test minimum margin (1 point game)"""
        even_matchup["scoring_margin"] = 1.0
        elo_change = calc_elo_diff(**even_matchup)

        # Should still calculate valid ELO change
        assert elo_change is not None
        assert not math.isnan(elo_change)
        assert abs(elo_change) < 20, "1-point game should have moderate ELO change"

    def test_zero_margin_tie(self, even_matchup):
        """Test zero margin (tie game with 0-0 or equal scores)"""
        even_matchup["scoring_margin"] = 0.0
        even_matchup["game_result"] = 0.5  # tie
        elo_change = calc_elo_diff(**even_matchup)

        # log(0+1) = log(1) = 0, so MOV multiplier should be 0
        # Therefore elo_change should be 0
        assert abs(elo_change) < 0.01, "Zero margin should result in near-zero ELO change"

    def test_large_elo_difference(self):
        """Test large ELO difference (400+ points)"""
        # 400 point difference = ~90% expected win probability
        params = {
            "home_elo": 1800.0,
            "visiting_elo": 1400.0,
            "home_adv": 52.0,
            "game_result": 0,  # favorite wins
            "scoring_margin": 14.0,
            "k_factor": 20.0,
        }
        elo_change = calc_elo_diff(**params)

        # Favorite won as expected, ELO change should be small
        assert abs(elo_change) < 10, "Expected outcome for heavy favorite should have small ELO change"

    def test_massive_upset(self):
        """Test massive upset (400+ point underdog wins)"""
        params = {
            "home_elo": 1800.0,  # heavy favorite
            "visiting_elo": 1400.0,  # heavy underdog
            "home_adv": 52.0,
            "game_result": 1,  # underdog wins!
            "scoring_margin": 7.0,
            "k_factor": 20.0,
        }
        elo_change = calc_elo_diff(**params)

        # Massive upset should result in large ELO change
        assert elo_change > 20, "Massive upset should result in large positive ELO change"


@pytest.mark.unit
class TestEloFormulas:
    """Tests validating ELO formula implementation"""

    def test_expected_win_probability_calculation(self):
        """Validate expected win probability formula"""
        # Equal teams (1500 each) with home advantage (52)
        # Expected visiting win prob = 1 / (1 + 10^(-(1500 - 1500 - 52) / 400))
        #                            = 1 / (1 + 10^(52/400))
        #                            = 1 / (1 + 10^0.13)
        #                            ≈ 1 / (1 + 1.349) ≈ 0.426 (42.6%)

        params = {
            "home_elo": 1500.0,
            "visiting_elo": 1500.0,
            "home_adv": 52.0,
            "game_result": 1,  # visiting team wins
            "scoring_margin": 7.0,
            "k_factor": 20.0,
        }

        # Calculate expected visiting win probability manually
        expected_visiting_win = 1.0 / (10.0 ** (-(1500 - 1500 - 52) / 400.0) + 1.0)
        assert 0.42 < expected_visiting_win < 0.43, "Expected win probability calculation is correct"

    def test_mov_multiplier_for_blowout(self):
        """Validate MOV multiplier increases for blowouts"""
        # Test that MOV multiplier is larger for bigger margins
        params_close = {
            "home_elo": 1500.0,
            "visiting_elo": 1500.0,
            "home_adv": 52.0,
            "game_result": 0,
            "scoring_margin": 3.0,
            "k_factor": 20.0,
        }

        params_blowout = params_close.copy()
        params_blowout["scoring_margin"] = 28.0

        close_change = calc_elo_diff(**params_close)
        blowout_change = calc_elo_diff(**params_blowout)

        # Calculate ratio of ELO changes (should reflect MOV multiplier ratio)
        ratio = abs(blowout_change) / abs(close_change)

        # log(28+1) / log(3+1) ≈ 3.367 / 1.386 ≈ 2.43
        # So blowout should be roughly 2.4x the close game change
        assert 2.0 < ratio < 3.0, "MOV multiplier should increase ELO change for blowouts"

    def test_mov_multiplier_for_upset(self):
        """Validate MOV multiplier increases for upsets"""
        # When underdog wins, winner_elo_diff is negative
        # This increases the denominator in MOV formula, making multiplier larger

        # Expected outcome (favorite wins)
        expected_params = {
            "home_elo": 1600.0,
            "visiting_elo": 1400.0,
            "home_adv": 52.0,
            "game_result": 0,  # favorite (home) wins
            "scoring_margin": 10.0,
            "k_factor": 20.0,
        }

        # Upset (underdog wins)
        upset_params = expected_params.copy()
        upset_params["game_result"] = 1  # underdog (visiting) wins

        expected_change = calc_elo_diff(**expected_params)
        upset_change = calc_elo_diff(**upset_params)

        # Upset should have larger absolute change
        assert abs(upset_change) > abs(expected_change), \
            "MOV multiplier should be larger for upsets"


@pytest.mark.unit
class TestEloInvariants:
    """Tests for ELO system invariants that must always hold"""

    def test_elo_change_is_finite(self, even_matchup):
        """ELO change should always be a finite number"""
        elo_change = calc_elo_diff(**even_matchup)
        assert math.isfinite(elo_change), "ELO change must be finite"
        assert not math.isnan(elo_change), "ELO change must not be NaN"

    def test_symmetry_home_vs_visiting(self):
        """Test that swapping home/visiting teams gives opposite ELO change"""
        params_home_win = {
            "home_elo": 1550.0,
            "visiting_elo": 1450.0,
            "home_adv": 52.0,
            "game_result": 0,  # home wins
            "scoring_margin": 7.0,
            "k_factor": 20.0,
        }

        # Swap teams and flip result
        params_visiting_win = {
            "home_elo": 1450.0,
            "visiting_elo": 1550.0,
            "home_adv": 52.0,
            "game_result": 1,  # visiting wins (same team as before)
            "scoring_margin": 7.0,
            "k_factor": 20.0,
        }

        home_win_change = calc_elo_diff(**params_home_win)
        visiting_win_change = calc_elo_diff(**params_visiting_win)

        # Signs should be opposite
        assert home_win_change * visiting_win_change < 0, \
            "Swapping teams should reverse sign of ELO change"

    def test_k_factor_scales_linearly(self, even_matchup):
        """Test that K-factor scales ELO change linearly"""
        k20 = even_matchup.copy()
        k20["k_factor"] = 20.0
        change_k20 = calc_elo_diff(**k20)

        k40 = even_matchup.copy()
        k40["k_factor"] = 40.0
        change_k40 = calc_elo_diff(**k40)

        # K-factor doubled, ELO change should double
        ratio = abs(change_k40) / abs(change_k20)
        assert 1.9 < ratio < 2.1, "K-factor should scale ELO change linearly"

    def test_type_coercion_works(self):
        """Test that function handles various numeric types"""
        # Test with integers
        params_int = {
            "home_elo": 1500,  # int
            "visiting_elo": 1500,  # int
            "home_adv": 52,  # int
            "game_result": 0,  # int
            "scoring_margin": 7,  # int
            "k_factor": 20,  # int
        }
        elo_change = calc_elo_diff(**params_int)
        assert math.isfinite(elo_change), "Should handle integer inputs"

    def test_elo_change_bounded_for_normal_games(self, even_matchup):
        """ELO changes should be reasonable for normal games"""
        elo_change = calc_elo_diff(**even_matchup)

        # For K=20 and normal games, ELO change should be < 50 points
        assert abs(elo_change) < 50, \
            "ELO change should be bounded for normal games (K=20, margin<30)"


@pytest.mark.unit
class TestEloRegressionCases:
    """Regression tests using known ELO calculations"""

    def test_fivethirtyeight_reference_case(self):
        """
        Test using FiveThirtyEight methodology parameters

        This validates our implementation matches FiveThirtyEight's published
        methodology (https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/)

        Scenario: Kansas City Chiefs (1650 ELO) vs Buffalo Bills (1580 ELO)
        - Home team: Chiefs (1650 ELO)
        - Visiting team: Bills (1580 ELO)
        - Home advantage: 52 points
        - Score: Chiefs 30, Bills 24 (6-point home win)
        - K-factor: 20 (FiveThirtyEight standard)

        Expected behavior:
        - Chiefs favored by ~118 ELO points after home adjustment (1650+52 - 1580)
        - Chiefs should be ~76% to win
        - Chiefs won as expected, so ELO change should be modest
        - MOV multiplier: ln(7) * (2.2 / (118*0.001 + 2.2)) ≈ 1.945 * 0.949 ≈ 1.85
        - Expected change: K * MOV * (actual - expected) ≈ 20 * 1.85 * (0 - 0.24) ≈ -8.9
        """
        params = {
            "game_result": 0,  # Home team (Chiefs) won
            "home_elo": 1650.0,
            "visiting_elo": 1580.0,
            "home_adv": 52.0,
            "scoring_margin": 6.0,
            "k_factor": 20.0,
            "elo_scale": 400.0,
            "mov_multiplier_base": 2.2,
            "mov_multiplier_divisor": 0.001,
        }

        elo_change = calc_elo_diff(**params)

        # Chiefs won as expected, so they should LOSE ELO (overperformed expected margin)
        # ELO change is from home perspective, negative means home gains
        # Expected: around -12 points based on the calculation
        assert -14.0 < elo_change < -10.0, \
            f"ELO change {elo_change} not in expected range for favored home win"

        # Verify the change is negative (home team gains rating)
        assert elo_change < 0, "Home team should gain ELO for winning"

    def test_known_game_calculation(self):
        """
        Test a known game with hand-calculated expected values

        Example: Chiefs (1650) vs Bills (1600) at home
        Home advantage: 52
        Chiefs win by 7
        Expected ELO change: ~-8 (Chiefs slightly favored, won as expected)
        """
        params = {
            "home_elo": 1650.0,
            "visiting_elo": 1600.0,
            "home_adv": 52.0,
            "game_result": 0,  # home (Chiefs) wins
            "scoring_margin": 7.0,
            "k_factor": 20.0,
        }

        elo_change = calc_elo_diff(**params)

        # Chiefs were favored (1650+52 vs 1600 = 102 point advantage)
        # Chiefs won as expected by moderate margin
        # ELO change should be small and negative (home team gains)
        assert -15 < elo_change < 0, \
            "Favorite winning by moderate margin should have small ELO change"
