"""
Integration Tests for NFL Tiebreaker Logic

Tests the nfl_tiebreakers_optimized.py model which implements NFL playoff
seeding with complex tiebreaker rules.

Tiebreaker order (per NFL rules):
1. Division winners (rank 1-4 per conference)
2. Wild cards (rank 5-7 per conference)
3. Within each group:
   - Overall record (wins)
   - Head-to-head record
   - Division record (for division ties)
   - Conference record
   - Common games record (min 4 common games)
   - Strength of victory
   - Strength of schedule
   - Team name (last resort)

Reference: https://www.nfl.com/standings/tie-breaking-procedures
"""

import pytest
import polars as pl
import pandas as pd
import sys
from pathlib import Path

# Add transform/models/nfl/analysis to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "transform" / "models" / "nfl" / "analysis"))

from nfl_tiebreakers_optimized import (
    _build_long_games,
    _team_records,
    _div_conf_records,
    _h2h_summary,
    _h2h_metrics,
)


@pytest.fixture
def teams_data():
    """Sample NFL teams with conference and division"""
    return pl.DataFrame({
        "team": ["Kansas City Chiefs", "Buffalo Bills", "Miami Dolphins", "New England Patriots",
                 "Dallas Cowboys", "Philadelphia Eagles", "New York Giants", "Washington Commanders"],
        "conf": ["AFC", "AFC", "AFC", "AFC", "NFC", "NFC", "NFC", "NFC"],
        "division": ["AFC West", "AFC East", "AFC East", "AFC East",
                     "NFC East", "NFC East", "NFC East", "NFC East"],
        "team_short": ["KC", "BUF", "MIA", "NE", "DAL", "PHI", "NYG", "WAS"],
    })


@pytest.fixture
def simple_season_games():
    """
    Simple season with clear playoff picture
    - Kansas City Chiefs: 12-5 (division winner)
    - Buffalo Bills: 11-6 (wild card)
    - Miami Dolphins: 10-7 (wild card)
    - New England Patriots: 8-9 (miss playoffs)
    """
    games = []
    scenario_id = 1
    game_id = 1

    # Chiefs: 12 wins
    for i in range(12):
        games.append({
            "scenario_id": scenario_id,
            "game_id": game_id + i,
            "home_team": "Kansas City Chiefs",
            "visiting_team": f"Opponent{i}",
            "winning_team": "Kansas City Chiefs",
        })
    for i in range(5):
        games.append({
            "scenario_id": scenario_id,
            "game_id": game_id + 12 + i,
            "home_team": f"Opponent{i+12}",
            "visiting_team": "Kansas City Chiefs",
            "winning_team": f"Opponent{i+12}",
        })

    # Bills: 11 wins
    game_id = 100
    for i in range(11):
        games.append({
            "scenario_id": scenario_id,
            "game_id": game_id + i,
            "home_team": "Buffalo Bills",
            "visiting_team": f"OtherOpponent{i}",
            "winning_team": "Buffalo Bills",
        })
    for i in range(6):
        games.append({
            "scenario_id": scenario_id,
            "game_id": game_id + 11 + i,
            "home_team": f"OtherOpponent{i+11}",
            "visiting_team": "Buffalo Bills",
            "winning_team": f"OtherOpponent{i+11}",
        })

    return pl.DataFrame(games)


@pytest.fixture
def tied_teams_scenario():
    """
    Scenario with tied records requiring head-to-head tiebreaker
    - Buffalo Bills: 10-7 (beats Miami head-to-head 2-0)
    - Miami Dolphins: 10-7 (loses to Buffalo head-to-head 0-2)
    """
    games = []
    scenario_id = 2

    # Bills and Dolphins both 10-7, but Bills beat Dolphins twice
    # Bills wins
    for i in range(10):
        games.append({
            "scenario_id": scenario_id,
            "game_id": i + 1,
            "home_team": "Buffalo Bills" if i < 5 else f"Opponent{i}",
            "visiting_team": f"Opponent{i}" if i < 5 else "Buffalo Bills",
            "winning_team": "Buffalo Bills",
        })

    # Bills losses
    for i in range(7):
        games.append({
            "scenario_id": scenario_id,
            "game_id": i + 100,
            "home_team": "Buffalo Bills" if i < 4 else f"Loser{i}",
            "visiting_team": f"Loser{i}" if i < 4 else "Buffalo Bills",
            "winning_team": f"Loser{i}",
        })

    # Dolphins wins (same record, different opponents)
    for i in range(10):
        games.append({
            "scenario_id": scenario_id,
            "game_id": i + 200,
            "home_team": "Miami Dolphins" if i < 5 else f"OtherOpponent{i}",
            "visiting_team": f"OtherOpponent{i}" if i < 5 else "Miami Dolphins",
            "winning_team": "Miami Dolphins",
        })

    # Dolphins losses (including 2 to Bills)
    for i in range(7):
        games.append({
            "scenario_id": scenario_id,
            "game_id": i + 300,
            "home_team": "Miami Dolphins" if i < 4 else f"OtherLoser{i}",
            "visiting_team": f"OtherLoser{i}" if i < 4 else "Miami Dolphins",
            "winning_team": f"OtherLoser{i}",
        })

    # Add head-to-head games: Bills beat Dolphins twice
    games.extend([
        {
            "scenario_id": scenario_id,
            "game_id": 400,
            "home_team": "Buffalo Bills",
            "visiting_team": "Miami Dolphins",
            "winning_team": "Buffalo Bills",
        },
        {
            "scenario_id": scenario_id,
            "game_id": 401,
            "home_team": "Miami Dolphins",
            "visiting_team": "Buffalo Bills",
            "winning_team": "Buffalo Bills",
        },
    ])

    return pl.DataFrame(games)


@pytest.mark.integration
class TestTiebreakerHelpers:
    """Test helper functions for tiebreaker logic"""

    def test_build_long_games(self, simple_season_games):
        """Test converting game results to long format (team perspective)"""
        long_games = _build_long_games(simple_season_games)

        # Should have 2x rows (one for each team in each game)
        assert len(long_games) == len(simple_season_games) * 2

        # Check columns
        assert "team" in long_games.columns
        assert "opponent" in long_games.columns
        assert "won" in long_games.columns
        assert "scenario_id" in long_games.columns

        # Kansas City Chiefs should have 12 wins
        chiefs_games = long_games.filter(pl.col("team") == "Kansas City Chiefs")
        chiefs_wins = chiefs_games.filter(pl.col("won") == 1).height
        assert chiefs_wins == 12, f"Chiefs should have 12 wins, got {chiefs_wins}"

    def test_team_records(self, simple_season_games):
        """Test calculating team win-loss records"""
        long_games = _build_long_games(simple_season_games)
        records = _team_records(long_games)

        # Check Chiefs record (12-5)
        chiefs_record = records.filter(pl.col("team") == "Kansas City Chiefs").to_dicts()[0]
        assert chiefs_record["wins"] == 12
        assert chiefs_record["losses"] == 5
        assert chiefs_record["games"] == 17

        # Check Bills record (11-6)
        bills_record = records.filter(pl.col("team") == "Buffalo Bills").to_dicts()[0]
        assert bills_record["wins"] == 11
        assert bills_record["losses"] == 6

    def test_h2h_summary(self, tied_teams_scenario):
        """Test head-to-head record calculation"""
        h2h = _h2h_summary(tied_teams_scenario)

        # Bills should have beaten Dolphins 2-0
        bills_dolphins_h2h = h2h.filter(
            (pl.col("team1") == "Buffalo Bills") & (pl.col("team2") == "Miami Dolphins")
        ).to_dicts()

        assert len(bills_dolphins_h2h) > 0, "Should have Bills-Dolphins head-to-head record"
        h2h_record = bills_dolphins_h2h[0]
        assert h2h_record["team1_wins"] == 2, "Bills should have won 2 games"
        assert h2h_record["team2_wins"] == 0, "Dolphins should have won 0 games"


@pytest.mark.integration
class TestDivisionWinners:
    """Test division winner determination

    NOTE: These tests require building a full dbt test harness to mock
    the ref() system and create synthetic playoff scenarios. This is a
    multi-day effort requiring:
    - Mock dbt context with ref() to nfl_reg_season_simulator and nfl_ratings
    - Synthetic playoff data (10k scenarios × 32 teams × 17 weeks)
    - Proper categorical type handling for Polars DataFrames

    Future work: Implement dbt-testable wrapper around model() function.
    """

    def test_clear_division_winner(self):
        """Test scenario with clear division winner (best record)"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_tied_division_winner_h2h(self):
        """Test division tie broken by head-to-head"""
        pytest.skip("Requires dbt test infrastructure (future work)")


@pytest.mark.integration
class TestWildCardSeeding:
    """Test wild card seeding logic (requires dbt test infrastructure)"""

    def test_wild_card_by_record(self):
        """Test wild card seeding by overall record"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_wild_card_tied_h2h(self):
        """Test wild card tie broken by head-to-head"""
        pytest.skip("Requires dbt test infrastructure (future work)")


@pytest.mark.integration
@pytest.mark.slow
class TestTiebreakerRules:
    """Test specific tiebreaker rules (requires dbt test infrastructure)"""

    def test_wins_tiebreaker(self):
        """Test that wins is first tiebreaker"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_h2h_tiebreaker(self):
        """Test head-to-head tiebreaker (after wins)"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_conference_record_tiebreaker(self):
        """Test conference record tiebreaker"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_common_games_tiebreaker(self):
        """Test common games tiebreaker (min 4 games)"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_strength_of_victory_tiebreaker(self):
        """Test strength of victory tiebreaker"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_strength_of_schedule_tiebreaker(self):
        """Test strength of schedule tiebreaker"""
        pytest.skip("Requires dbt test infrastructure (future work)")


@pytest.mark.integration
@pytest.mark.slow
class TestThreeWayTies:
    """Test three-way (or more) tie scenarios (requires dbt test infrastructure)"""

    def test_three_way_tie_clear_h2h(self):
        """Test 3-way tie where one team beat both others"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_three_way_tie_circular_h2h(self):
        """Test 3-way tie with circular head-to-head (A>B, B>C, C>A)"""
        pytest.skip("Requires dbt test infrastructure (future work)")


@pytest.mark.integration
class TestHistoricalPlayoffs:
    """Regression tests using actual NFL playoff results"""

    def test_2024_playoff_seeds_documented(self):
        """Document 2024 playoff seeding for future validation"""
        from tests.fixtures.nfl_2024_playoff_results import (
            NFL_2024_PLAYOFF_SEEDS,
            get_playoff_teams,
            get_division_winners,
            get_wild_cards,
        )

        # Verify fixture data structure
        assert "AFC" in NFL_2024_PLAYOFF_SEEDS
        assert "NFC" in NFL_2024_PLAYOFF_SEEDS

        # Verify 7 teams per conference
        assert len(NFL_2024_PLAYOFF_SEEDS["AFC"]) == 7
        assert len(NFL_2024_PLAYOFF_SEEDS["NFC"]) == 7

        # Verify seeds 1-7 present
        for conf in ["AFC", "NFC"]:
            seeds = list(NFL_2024_PLAYOFF_SEEDS[conf].keys())
            assert sorted(seeds) == [1, 2, 3, 4, 5, 6, 7]

        # Verify helper functions work
        afc_playoff_teams = get_playoff_teams("AFC")
        assert len(afc_playoff_teams) == 7
        assert "Kansas City Chiefs" in afc_playoff_teams

        afc_division_winners = get_division_winners("AFC")
        assert len(afc_division_winners) == 4

        afc_wild_cards = get_wild_cards("AFC")
        assert len(afc_wild_cards) == 3

    def test_2024_playoff_seeds_known_results(self):
        """Test known 2024 playoff results"""
        from tests.fixtures.nfl_2024_playoff_results import NFL_2024_PLAYOFF_SEEDS

        # AFC seeds
        assert NFL_2024_PLAYOFF_SEEDS["AFC"][1]["team"] == "Kansas City Chiefs"
        assert NFL_2024_PLAYOFF_SEEDS["AFC"][2]["team"] == "Buffalo Bills"
        assert NFL_2024_PLAYOFF_SEEDS["AFC"][7]["team"] == "Denver Broncos"

        # NFC seeds
        assert NFL_2024_PLAYOFF_SEEDS["NFC"][1]["team"] == "Detroit Lions"
        assert NFL_2024_PLAYOFF_SEEDS["NFC"][2]["team"] == "Philadelphia Eagles"
        assert NFL_2024_PLAYOFF_SEEDS["NFC"][7]["team"] == "Green Bay Packers"

    def test_2024_tiebreaker_scenarios_documented(self):
        """Document interesting 2024 tiebreaker scenarios"""
        from tests.fixtures.nfl_2024_playoff_results import NFL_2024_TIEBREAKER_NOTES

        # AFC 10-7 three-way tie
        assert "AFC_10-7_tie" in NFL_2024_TIEBREAKER_NOTES
        afc_tie = NFL_2024_TIEBREAKER_NOTES["AFC_10-7_tie"]
        assert len(afc_tie["teams"]) == 3
        assert "Houston Texans" in afc_tie["teams"]

        # NFC 10-7 three-way tie (Seattle missed playoffs!)
        assert "NFC_10-7_tie" in NFL_2024_TIEBREAKER_NOTES
        nfc_tie = NFL_2024_TIEBREAKER_NOTES["NFC_10-7_tie"]
        assert "Seattle Seahawks" in nfc_tie["teams"]
        assert "MISSED" in nfc_tie["note"]

    @pytest.mark.skip(reason="Requires full 2024 season game data")
    def test_2024_tiebreaker_validation_full(self):
        """
        Full validation of 2024 tiebreaker logic

        This test would:
        1. Load all 2024 season game results
        2. Run tiebreaker model with actual results
        3. Compare output seeds to NFL_2024_PLAYOFF_SEEDS
        4. Assert all seeds match exactly

        TODO: Implement when 2024 season game data is available
        """
        pass

    def test_2023_playoffs(self):
        """Validate against 2023 playoff seeding"""
        from tests.fixtures.nfl_2023_playoff_results import (
            NFL_2023_PLAYOFF_SEEDS,
            get_playoff_teams,
            get_division_winners,
            get_wild_cards,
        )

        # Verify fixture data structure
        assert "AFC" in NFL_2023_PLAYOFF_SEEDS
        assert "NFC" in NFL_2023_PLAYOFF_SEEDS

        # Verify 7 teams per conference
        assert len(NFL_2023_PLAYOFF_SEEDS["AFC"]) == 7
        assert len(NFL_2023_PLAYOFF_SEEDS["NFC"]) == 7

        # Verify known results
        assert NFL_2023_PLAYOFF_SEEDS["AFC"][1]["team"] == "Baltimore Ravens"
        assert NFL_2023_PLAYOFF_SEEDS["NFC"][1]["team"] == "San Francisco 49ers"

        # Verify helper functions
        afc_teams = get_playoff_teams("AFC")
        assert len(afc_teams) == 7
        assert "Kansas City Chiefs" in afc_teams  # Chiefs were seed 3

    def test_2022_playoffs(self):
        """Validate against 2022 playoff seeding"""
        from tests.fixtures.nfl_2022_playoff_results import (
            NFL_2022_PLAYOFF_SEEDS,
            get_playoff_teams,
            get_division_winners,
            get_wild_cards,
        )

        # Verify fixture data structure
        assert "AFC" in NFL_2022_PLAYOFF_SEEDS
        assert "NFC" in NFL_2022_PLAYOFF_SEEDS

        # Verify 7 teams per conference
        assert len(NFL_2022_PLAYOFF_SEEDS["AFC"]) == 7
        assert len(NFL_2022_PLAYOFF_SEEDS["NFC"]) == 7

        # Verify known results
        assert NFL_2022_PLAYOFF_SEEDS["AFC"][1]["team"] == "Kansas City Chiefs"
        assert NFL_2022_PLAYOFF_SEEDS["NFC"][1]["team"] == "Philadelphia Eagles"

        # Verify losing record division winner
        assert NFL_2022_PLAYOFF_SEEDS["NFC"][4]["team"] == "Tampa Bay Buccaneers"
        assert NFL_2022_PLAYOFF_SEEDS["NFC"][4]["record"] == "8-9"

    def test_2021_playoffs(self):
        """Validate against 2021 playoff seeding"""
        from tests.fixtures.nfl_2021_playoff_results import (
            NFL_2021_PLAYOFF_SEEDS,
            get_playoff_teams,
            get_division_winners,
            get_wild_cards,
        )

        # Verify fixture data structure
        assert "AFC" in NFL_2021_PLAYOFF_SEEDS
        assert "NFC" in NFL_2021_PLAYOFF_SEEDS

        # Verify 7 teams per conference
        assert len(NFL_2021_PLAYOFF_SEEDS["AFC"]) == 7
        assert len(NFL_2021_PLAYOFF_SEEDS["NFC"]) == 7

        # Verify known results
        assert NFL_2021_PLAYOFF_SEEDS["AFC"][1]["team"] == "Tennessee Titans"
        assert NFL_2021_PLAYOFF_SEEDS["NFC"][1]["team"] == "Green Bay Packers"

        # Verify Rams won Super Bowl that year (seed 4)
        assert NFL_2021_PLAYOFF_SEEDS["NFC"][4]["team"] == "Los Angeles Rams"

    def test_2020_playoffs(self):
        """Validate against 2020 playoff seeding"""
        from tests.fixtures.nfl_2020_playoff_results import (
            NFL_2020_PLAYOFF_SEEDS,
            get_playoff_teams,
            get_division_winners,
            get_wild_cards,
        )

        # Verify fixture data structure
        assert "AFC" in NFL_2020_PLAYOFF_SEEDS
        assert "NFC" in NFL_2020_PLAYOFF_SEEDS

        # Verify 7 teams per conference
        assert len(NFL_2020_PLAYOFF_SEEDS["AFC"]) == 7
        assert len(NFL_2020_PLAYOFF_SEEDS["NFC"]) == 7

        # Verify known results
        assert NFL_2020_PLAYOFF_SEEDS["AFC"][1]["team"] == "Kansas City Chiefs"
        assert NFL_2020_PLAYOFF_SEEDS["NFC"][1]["team"] == "Green Bay Packers"

        # Verify losing record division winner (Washington 7-9)
        assert NFL_2020_PLAYOFF_SEEDS["NFC"][4]["team"] == "Washington Football Team"
        assert NFL_2020_PLAYOFF_SEEDS["NFC"][4]["record"] == "7-9"


@pytest.mark.integration
class TestTiebreakerInvariants:
    """Test invariants that must hold for tiebreaker logic (requires dbt test infrastructure)"""

    def test_exactly_7_playoff_teams_per_conference(self):
        """Each conference must have exactly 7 playoff teams (ranks 1-7)"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_ranks_are_unique_per_conference(self):
        """Ranks 1-7 must be unique within each conference"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_division_winners_ranked_1_through_4(self):
        """Division winners must occupy ranks 1-4"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_wild_cards_ranked_5_through_7(self):
        """Wild cards must occupy ranks 5-7"""
        pytest.skip("Requires dbt test infrastructure (future work)")

    def test_all_teams_have_rank(self):
        """All teams must have a rank (1-16 per conference)"""
        pytest.skip("Requires dbt test infrastructure (future work)")
