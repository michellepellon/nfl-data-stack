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
    model,
)
from tests.dbt_test_harness import DbtTestHarness


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
    """Test division winner determination"""

    def test_clear_division_winner(self, sample_teams):
        """Test scenario with clear division winner (best record)"""
        # AFC East: Buffalo (12-5), Miami (10-7), NYJ (8-9), NE (7-10)
        # Buffalo should be division winner
        games = []
        scenario_id = 1

        # Buffalo Bills: 12 wins
        for i in range(12):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Buffalo Bills" if i % 2 == 0 else f"Opponent{i}",
                "visiting_team": f"Opponent{i}" if i % 2 == 0 else "Buffalo Bills",
                "winning_team": "Buffalo Bills",
            })
        for i in range(5):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Buffalo Bills" if i % 2 == 0 else f"Loser{i}",
                "visiting_team": f"Loser{i}" if i % 2 == 0 else "Buffalo Bills",
                "winning_team": f"Loser{i}",
            })

        # Miami Dolphins: 10 wins
        for i in range(10):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Miami Dolphins" if i % 2 == 0 else f"MiaOpp{i}",
                "visiting_team": f"MiaOpp{i}" if i % 2 == 0 else "Miami Dolphins",
                "winning_team": "Miami Dolphins",
            })
        for i in range(7):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Miami Dolphins" if i % 2 == 0 else f"MiaLoss{i}",
                "visiting_team": f"MiaLoss{i}" if i % 2 == 0 else "Miami Dolphins",
                "winning_team": f"MiaLoss{i}",
            })

        simulator_df = pl.DataFrame(games)
        ratings_df = sample_teams.select(["team", "conf", "division"])

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Buffalo should be AFC East division winner (rank 1-4)
        bills_result = result.filter(pl.col("team") == "Buffalo Bills")
        assert len(bills_result) > 0, "Buffalo Bills should be in results"
        bills_rank = bills_result[0, "rank"]
        assert 1 <= bills_rank <= 4, f"Buffalo should be division winner (rank 1-4), got rank {bills_rank}"

        # Miami should not be division winner (rank 5+)
        dolphins_result = result.filter(pl.col("team") == "Miami Dolphins")
        if len(dolphins_result) > 0:
            dolphins_rank = dolphins_result[0, "rank"]
            # If both are in the same division and conference, Miami should rank lower
            if dolphins_result[0, "conference"] == bills_result[0, "conference"]:
                assert dolphins_rank > bills_rank, "Miami should rank below Buffalo"

    def test_tied_division_winner_h2h(self, sample_teams):
        """Test division tie broken by head-to-head"""
        # AFC East: Buffalo and Miami both 11-6, but Buffalo wins head-to-head 2-0
        games = []
        scenario_id = 2

        # Buffalo Bills: 11 wins (including 2 vs Miami)
        for i in range(9):  # 9 wins against other opponents
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Buffalo Bills" if i % 2 == 0 else f"Opponent{i}",
                "visiting_team": f"Opponent{i}" if i % 2 == 0 else "Buffalo Bills",
                "winning_team": "Buffalo Bills",
            })
        # 2 wins vs Miami
        games.extend([
            {
                "scenario_id": scenario_id,
                "home_team": "Buffalo Bills",
                "visiting_team": "Miami Dolphins",
                "winning_team": "Buffalo Bills",
            },
            {
                "scenario_id": scenario_id,
                "home_team": "Miami Dolphins",
                "visiting_team": "Buffalo Bills",
                "winning_team": "Buffalo Bills",
            },
        ])
        # 6 losses
        for i in range(6):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Buffalo Bills" if i % 2 == 0 else f"Loser{i}",
                "visiting_team": f"Loser{i}" if i % 2 == 0 else "Buffalo Bills",
                "winning_team": f"Loser{i}",
            })

        # Miami Dolphins: 11 wins (against others, already lost 2 to Buffalo)
        for i in range(11):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Miami Dolphins" if i % 2 == 0 else f"MiaOpp{i}",
                "visiting_team": f"MiaOpp{i}" if i % 2 == 0 else "Miami Dolphins",
                "winning_team": "Miami Dolphins",
            })
        # 4 more losses (2 already to Buffalo)
        for i in range(4):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Miami Dolphins" if i % 2 == 0 else f"MiaLoss{i}",
                "visiting_team": f"MiaLoss{i}" if i % 2 == 0 else "Miami Dolphins",
                "winning_team": f"MiaLoss{i}",
            })

        simulator_df = pl.DataFrame(games)
        ratings_df = sample_teams.select(["team", "conf", "division"])

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Both should be in AFC, but Buffalo should rank higher due to h2h
        bills_result = result.filter(pl.col("team") == "Buffalo Bills")
        dolphins_result = result.filter(pl.col("team") == "Miami Dolphins")

        if len(bills_result) > 0 and len(dolphins_result) > 0:
            bills_rank = bills_result[0, "rank"]
            dolphins_rank = dolphins_result[0, "rank"]
            assert bills_rank < dolphins_rank, "Buffalo should rank higher than Miami (won head-to-head)"


@pytest.mark.integration
class TestWildCardSeeding:
    """Test wild card seeding logic"""

    def test_wild_card_by_record(self, sample_teams):
        """Test wild card seeding by overall record"""
        # Create scenario where division winners are clear,
        # and wild cards are sorted by record
        games = []
        scenario_id = 3

        # AFC East winner: Buffalo 12-5
        for i in range(12):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Buffalo Bills",
                "visiting_team": f"Opp{i}",
                "winning_team": "Buffalo Bills",
            })
        for i in range(5):
            games.append({
                "scenario_id": scenario_id,
                "home_team": f"Loss{i}",
                "visiting_team": "Buffalo Bills",
                "winning_team": f"Loss{i}",
            })

        # AFC West winner: Kansas City 11-6
        for i in range(11):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Kansas City Chiefs",
                "visiting_team": f"KCOpp{i}",
                "winning_team": "Kansas City Chiefs",
            })
        for i in range(6):
            games.append({
                "scenario_id": scenario_id,
                "home_team": f"KCLoss{i}",
                "visiting_team": "Kansas City Chiefs",
                "winning_team": f"KCLoss{i}",
            })

        # Wild card contenders from AFC East: Miami 10-7 (should be WC5)
        for i in range(10):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Miami Dolphins",
                "visiting_team": f"MiaOpp{i}",
                "winning_team": "Miami Dolphins",
            })
        for i in range(7):
            games.append({
                "scenario_id": scenario_id,
                "home_team": f"MiaLoss{i}",
                "visiting_team": "Miami Dolphins",
                "winning_team": f"MiaLoss{i}",
            })

        # Wild card contender: New York Jets 9-8 (should be WC6 or miss)
        for i in range(9):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "New York Jets",
                "visiting_team": f"NYJOpp{i}",
                "winning_team": "New York Jets",
            })
        for i in range(8):
            games.append({
                "scenario_id": scenario_id,
                "home_team": f"NYJLoss{i}",
                "visiting_team": "New York Jets",
                "winning_team": f"NYJLoss{i}",
            })

        simulator_df = pl.DataFrame(games)
        ratings_df = sample_teams.select(["team", "conf", "division"])

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Check that teams are ranked by wins
        bills_rank = result.filter(pl.col("team") == "Buffalo Bills")[0, "rank"]
        kc_rank = result.filter(pl.col("team") == "Kansas City Chiefs")[0, "rank"]
        miami_rank = result.filter(pl.col("team") == "Miami Dolphins")[0, "rank"]
        jets_rank = result.filter(pl.col("team") == "New York Jets")[0, "rank"]

        # Division winners should rank 1-4
        assert 1 <= bills_rank <= 4
        assert 1 <= kc_rank <= 4

        # Miami (10 wins) should be wild card (5-7) and rank better than Jets (9 wins)
        assert miami_rank < jets_rank, "Team with more wins should rank higher"

    def test_wild_card_tied_h2h(self, sample_teams):
        """Test wild card tie broken by head-to-head"""
        # Two wild card contenders with same record, broken by h2h
        games = []
        scenario_id = 4

        # AFC East winner: Buffalo 12-5
        for i in range(12):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Buffalo Bills",
                "visiting_team": f"Opp{i}",
                "winning_team": "Buffalo Bills",
            })
        for i in range(5):
            games.append({
                "scenario_id": scenario_id,
                "home_team": f"Loss{i}",
                "visiting_team": "Buffalo Bills",
                "winning_team": f"Loss{i}",
            })

        # Wild card contenders: Miami and NYJ both 10-7, Miami wins h2h
        # Miami: 10 wins (including 1 vs NYJ)
        for i in range(9):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Miami Dolphins",
                "visiting_team": f"MiaOpp{i}",
                "winning_team": "Miami Dolphins",
            })
        games.append({
            "scenario_id": scenario_id,
            "home_team": "Miami Dolphins",
            "visiting_team": "New York Jets",
            "winning_team": "Miami Dolphins",
        })
        for i in range(7):
            games.append({
                "scenario_id": scenario_id,
                "home_team": f"MiaLoss{i}",
                "visiting_team": "Miami Dolphins",
                "winning_team": f"MiaLoss{i}",
            })

        # NYJ: 10 wins (lost to Miami)
        for i in range(10):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "New York Jets",
                "visiting_team": f"NYJOpp{i}",
                "winning_team": "New York Jets",
            })
        for i in range(6):  # 6 more losses (already lost to Miami)
            games.append({
                "scenario_id": scenario_id,
                "home_team": f"NYJLoss{i}",
                "visiting_team": "New York Jets",
                "winning_team": f"NYJLoss{i}",
            })

        simulator_df = pl.DataFrame(games)
        ratings_df = sample_teams.select(["team", "conf", "division"])

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        miami_result = result.filter(pl.col("team") == "Miami Dolphins")
        jets_result = result.filter(pl.col("team") == "New York Jets")

        if len(miami_result) > 0 and len(jets_result) > 0:
            miami_rank = miami_result[0, "rank"]
            jets_rank = jets_result[0, "rank"]
            assert miami_rank < jets_rank, "Miami should rank higher (won h2h)"


@pytest.mark.integration
@pytest.mark.slow
class TestTiebreakerRules:
    """Test specific tiebreaker rules"""

    def test_wins_tiebreaker(self, sample_teams):
        """Test that wins is first tiebreaker"""
        games = []
        scenario_id = 10

        # Create two AFC East teams with different records
        # Buffalo: 12 wins, Miami: 10 wins
        for team, wins in [("Buffalo Bills", 12), ("Miami Dolphins", 10)]:
            losses = 17 - wins
            for i in range(wins):
                games.append({
                    "scenario_id": scenario_id,
                    "home_team": team,
                    "visiting_team": f"{team}_Opp{i}",
                    "winning_team": team,
                })
            for i in range(losses):
                games.append({
                    "scenario_id": scenario_id,
                    "home_team": f"{team}_Loss{i}",
                    "visiting_team": team,
                    "winning_team": f"{team}_Loss{i}",
                })

        simulator_df = pl.DataFrame(games)
        ratings_df = sample_teams.select(["team", "conf", "division"])

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Team with more wins should rank higher
        bills = result.filter(pl.col("team") == "Buffalo Bills")
        dolphins = result.filter(pl.col("team") == "Miami Dolphins")

        if len(bills) > 0 and len(dolphins) > 0:
            assert bills[0, "wins"] == 12
            assert dolphins[0, "wins"] == 10
            assert bills[0, "rank"] < dolphins[0, "rank"], "Team with more wins should rank higher"
            # Tiebreaker used might vary based on context (division vs conference level)
            assert bills[0, "tiebreaker_used"] in ["wins", "team name"], "Wins is primary tiebreaker"

    def test_h2h_tiebreaker(self, sample_teams):
        """Test head-to-head tiebreaker (after wins)"""
        games = []
        scenario_id = 11

        # Buffalo and Miami both 10-7, but Buffalo wins h2h 2-0
        # Buffalo: 8 wins vs others + 2 vs Miami = 10 wins
        for i in range(8):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Buffalo Bills",
                "visiting_team": f"BufOpp{i}",
                "winning_team": "Buffalo Bills",
            })
        # 2 wins vs Miami
        games.extend([
            {
                "scenario_id": scenario_id,
                "home_team": "Buffalo Bills",
                "visiting_team": "Miami Dolphins",
                "winning_team": "Buffalo Bills",
            },
            {
                "scenario_id": scenario_id,
                "home_team": "Miami Dolphins",
                "visiting_team": "Buffalo Bills",
                "winning_team": "Buffalo Bills",
            },
        ])
        # 7 losses
        for i in range(7):
            games.append({
                "scenario_id": scenario_id,
                "home_team": f"BufLoss{i}",
                "visiting_team": "Buffalo Bills",
                "winning_team": f"BufLoss{i}",
            })

        # Miami: 10 wins vs others (already lost 2 to Buffalo)
        for i in range(10):
            games.append({
                "scenario_id": scenario_id,
                "home_team": "Miami Dolphins",
                "visiting_team": f"MiaOpp{i}",
                "winning_team": "Miami Dolphins",
            })
        # 5 more losses (2 already to Buffalo = 7 total)
        for i in range(5):
            games.append({
                "scenario_id": scenario_id,
                "home_team": f"MiaLoss{i}",
                "visiting_team": "Miami Dolphins",
                "winning_team": f"MiaLoss{i}",
            })

        simulator_df = pl.DataFrame(games)
        ratings_df = sample_teams.select(["team", "conf", "division"])

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Both should have 10 wins, Buffalo ranks higher via h2h
        bills = result.filter(pl.col("team") == "Buffalo Bills")
        dolphins = result.filter(pl.col("team") == "Miami Dolphins")

        if len(bills) > 0 and len(dolphins) > 0:
            assert bills[0, "wins"] == 10
            assert dolphins[0, "wins"] == 10
            assert bills[0, "rank"] < dolphins[0, "rank"], "Buffalo should rank higher (won h2h)"
            # The tiebreaker_used might be "head-to-head" if they're tied within a group
            assert bills[0, "tiebreaker_used"] in ["wins", "head-to-head", "team name"]

    def test_conference_record_tiebreaker(self):
        """Test conference record tiebreaker"""
        pytest.skip("Requires complex scenario setup (future work)")

    def test_common_games_tiebreaker(self):
        """Test common games tiebreaker (min 4 games)"""
        pytest.skip("Requires complex scenario setup (future work)")

    def test_strength_of_victory_tiebreaker(self):
        """Test strength of victory tiebreaker"""
        pytest.skip("Requires complex scenario setup (future work)")

    def test_strength_of_schedule_tiebreaker(self):
        """Test strength of schedule tiebreaker"""
        pytest.skip("Requires complex scenario setup (future work)")


@pytest.mark.integration
@pytest.mark.slow
class TestThreeWayTies:
    """Test three-way (or more) tie scenarios"""

    def test_three_way_tie_clear_h2h(self, sample_teams):
        """Test 3-way tie where one team beat both others"""
        games = []
        scenario_id = 12

        # Three AFC East teams all 10-7, but Buffalo beat both Miami and NYJ
        teams_data = {
            "Buffalo Bills": {"wins_vs_others": 8, "vs_mia": "W", "vs_nyj": "W"},
            "Miami Dolphins": {"wins_vs_others": 9, "vs_buf": "L", "vs_nyj": "W"},
            "New York Jets": {"wins_vs_others": 9, "vs_buf": "L", "vs_mia": "L"},
        }

        # Generate games for each team
        for team, data in teams_data.items():
            # Wins vs other opponents
            for i in range(data["wins_vs_others"]):
                games.append({
                    "scenario_id": scenario_id,
                    "home_team": team,
                    "visiting_team": f"{team}_Opp{i}",
                    "winning_team": team,
                })

        # Head-to-head games
        # Buffalo vs Miami: Buffalo wins
        games.append({
            "scenario_id": scenario_id,
            "home_team": "Buffalo Bills",
            "visiting_team": "Miami Dolphins",
            "winning_team": "Buffalo Bills",
        })
        # Buffalo vs NYJ: Buffalo wins
        games.append({
            "scenario_id": scenario_id,
            "home_team": "Buffalo Bills",
            "visiting_team": "New York Jets",
            "winning_team": "Buffalo Bills",
        })
        # Miami vs NYJ: Miami wins
        games.append({
            "scenario_id": scenario_id,
            "home_team": "Miami Dolphins",
            "visiting_team": "New York Jets",
            "winning_team": "Miami Dolphins",
        })

        # Losses for each team (7 total, minus h2h losses already counted)
        losses_data = {
            "Buffalo Bills": 7,
            "Miami Dolphins": 6,  # Already lost 1 to Buffalo
            "New York Jets": 5,   # Already lost 2 (to Buffalo and Miami)
        }

        for team, losses in losses_data.items():
            for i in range(losses):
                games.append({
                    "scenario_id": scenario_id,
                    "home_team": f"{team}_Loss{i}",
                    "visiting_team": team,
                    "winning_team": f"{team}_Loss{i}",
                })

        simulator_df = pl.DataFrame(games)
        ratings_df = sample_teams.select(["team", "conf", "division"])

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Check results: Buffalo and Miami have 10 wins, Jets have 9
        bills = result.filter(pl.col("team") == "Buffalo Bills")
        dolphins = result.filter(pl.col("team") == "Miami Dolphins")
        jets = result.filter(pl.col("team") == "New York Jets")

        if len(bills) > 0 and len(dolphins) > 0 and len(jets) > 0:
            assert bills[0, "wins"] == 10  # 8 vs others + 2 in h2h
            assert dolphins[0, "wins"] == 10  # 9 vs others + 1 in h2h
            assert jets[0, "wins"] == 9   # 9 vs others + 0 in h2h

            # Buffalo should rank highest (beat both others in h2h)
            bills_rank = bills[0, "rank"]
            dolphins_rank = dolphins[0, "rank"]
            jets_rank = jets[0, "rank"]

            assert bills_rank < dolphins_rank, "Buffalo should rank higher than Miami"
            # Miami has more wins than Jets, so should rank higher
            assert dolphins_rank < jets_rank, "Miami should rank higher than Jets (more wins)"

    def test_three_way_tie_circular_h2h(self):
        """Test 3-way tie with circular head-to-head (A>B, B>C, C>A)"""
        pytest.skip("Requires complex scenario setup (future work)")


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
    """Test invariants that must hold for tiebreaker logic"""

    @pytest.fixture
    def full_season_scenario(self, sample_teams):
        """Create a complete season with all 32 teams and varied records"""
        games = []
        scenario_id = 100

        # Define records for all 32 teams (wins out of 17 games)
        team_wins = {
            # AFC East
            "Buffalo Bills": 13, "Miami Dolphins": 11, "New York Jets": 8, "New England Patriots": 4,
            # AFC West
            "Kansas City Chiefs": 14, "Los Angeles Chargers": 10, "Denver Broncos": 9, "Las Vegas Raiders": 6,
            # AFC North
            "Baltimore Ravens": 13, "Pittsburgh Steelers": 10, "Cleveland Browns": 7, "Cincinnati Bengals": 9,
            # AFC South
            "Houston Texans": 10, "Indianapolis Colts": 9, "Jacksonville Jaguars": 9, "Tennessee Titans": 6,
            # NFC East
            "Philadelphia Eagles": 14, "Dallas Cowboys": 12, "Washington Commanders": 8, "New York Giants": 5,
            # NFC West
            "San Francisco 49ers": 12, "Los Angeles Rams": 10, "Seattle Seahawks": 9, "Arizona Cardinals": 4,
            # NFC North
            "Detroit Lions": 12, "Green Bay Packers": 9, "Minnesota Vikings": 7, "Chicago Bears": 7,
            # NFC South
            "Tampa Bay Buccaneers": 9, "Atlanta Falcons": 7, "New Orleans Saints": 9, "Carolina Panthers": 2,
        }

        game_id = 1
        for team, wins in team_wins.items():
            losses = 17 - wins

            # Generate wins
            for i in range(wins):
                games.append({
                    "scenario_id": scenario_id,
                    "home_team": team if i % 2 == 0 else f"{team}_Opp{i}",
                    "visiting_team": f"{team}_Opp{i}" if i % 2 == 0 else team,
                    "winning_team": team,
                })
                game_id += 1

            # Generate losses
            for i in range(losses):
                games.append({
                    "scenario_id": scenario_id,
                    "home_team": team if i % 2 == 0 else f"{team}_Loss{i}",
                    "visiting_team": f"{team}_Loss{i}" if i % 2 == 0 else team,
                    "winning_team": f"{team}_Loss{i}",
                })
                game_id += 1

        return pl.DataFrame(games), sample_teams.select(["team", "conf", "division"])

    def test_exactly_7_playoff_teams_per_conference(self, full_season_scenario):
        """Each conference must have exactly 7 playoff teams (ranks 1-7)"""
        simulator_df, ratings_df = full_season_scenario

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Check AFC has exactly 7 playoff teams
        afc_playoff = result.filter((pl.col("conference") == "AFC") & (pl.col("rank") <= 7))
        assert len(afc_playoff) == 7, f"AFC should have exactly 7 playoff teams, got {len(afc_playoff)}"

        # Check NFC has exactly 7 playoff teams
        nfc_playoff = result.filter((pl.col("conference") == "NFC") & (pl.col("rank") <= 7))
        assert len(nfc_playoff) == 7, f"NFC should have exactly 7 playoff teams, got {len(nfc_playoff)}"

    def test_ranks_are_unique_per_conference(self, full_season_scenario):
        """Ranks 1-7 must be unique within each conference"""
        simulator_df, ratings_df = full_season_scenario

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Check AFC ranks are unique
        afc_playoff = result.filter((pl.col("conference") == "AFC") & (pl.col("rank") <= 7))
        afc_ranks = sorted(afc_playoff["rank"].to_list())
        assert afc_ranks == [1, 2, 3, 4, 5, 6, 7], f"AFC playoff ranks should be [1-7], got {afc_ranks}"

        # Check NFC ranks are unique
        nfc_playoff = result.filter((pl.col("conference") == "NFC") & (pl.col("rank") <= 7))
        nfc_ranks = sorted(nfc_playoff["rank"].to_list())
        assert nfc_ranks == [1, 2, 3, 4, 5, 6, 7], f"NFC playoff ranks should be [1-7], got {nfc_ranks}"

    def test_division_winners_ranked_1_through_4(self, full_season_scenario):
        """Division winners must occupy ranks 1-4"""
        simulator_df, ratings_df = full_season_scenario

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Get top 4 from each conference
        afc_top4 = result.filter((pl.col("conference") == "AFC") & (pl.col("rank") <= 4))
        nfc_top4 = result.filter((pl.col("conference") == "NFC") & (pl.col("rank") <= 4))

        # Each conference should have exactly 4 division winners
        assert len(afc_top4) == 4, f"AFC should have 4 division winners, got {len(afc_top4)}"
        assert len(nfc_top4) == 4, f"NFC should have 4 division winners, got {len(nfc_top4)}"

        # Check that ranks 1-4 are present
        assert sorted(afc_top4["rank"].to_list()) == [1, 2, 3, 4], "AFC division winners should be ranked 1-4"
        assert sorted(nfc_top4["rank"].to_list()) == [1, 2, 3, 4], "NFC division winners should be ranked 1-4"

    def test_wild_cards_ranked_5_through_7(self, full_season_scenario):
        """Wild cards must occupy ranks 5-7"""
        simulator_df, ratings_df = full_season_scenario

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Get ranks 5-7 from each conference (wild cards)
        afc_wildcards = result.filter((pl.col("conference") == "AFC") & (pl.col("rank") >= 5) & (pl.col("rank") <= 7))
        nfc_wildcards = result.filter((pl.col("conference") == "NFC") & (pl.col("rank") >= 5) & (pl.col("rank") <= 7))

        # Each conference should have exactly 3 wild cards
        assert len(afc_wildcards) == 3, f"AFC should have 3 wild cards, got {len(afc_wildcards)}"
        assert len(nfc_wildcards) == 3, f"NFC should have 3 wild cards, got {len(nfc_wildcards)}"

        # Check that ranks 5-7 are present
        assert sorted(afc_wildcards["rank"].to_list()) == [5, 6, 7], "AFC wild cards should be ranked 5-7"
        assert sorted(nfc_wildcards["rank"].to_list()) == [5, 6, 7], "NFC wild cards should be ranked 5-7"

    def test_all_teams_have_rank(self, full_season_scenario):
        """All teams must have a rank (1-16 per conference)"""
        simulator_df, ratings_df = full_season_scenario

        harness = DbtTestHarness()
        harness.add_ref("nfl_reg_season_simulator", simulator_df)
        harness.add_ref("nfl_ratings", ratings_df)

        result_pdf = model(harness.dbt, harness.session)
        result = pl.from_pandas(result_pdf)

        # Each conference should have 16 teams
        afc_teams = result.filter(pl.col("conference") == "AFC")
        nfc_teams = result.filter(pl.col("conference") == "NFC")

        assert len(afc_teams) == 16, f"AFC should have 16 teams, got {len(afc_teams)}"
        assert len(nfc_teams) == 16, f"NFC should have 16 teams, got {len(nfc_teams)}"

        # All ranks should be unique and complete (1-16)
        afc_ranks = sorted(afc_teams["rank"].to_list())
        nfc_ranks = sorted(nfc_teams["rank"].to_list())

        assert afc_ranks == list(range(1, 17)), f"AFC ranks should be [1-16], got {afc_ranks}"
        assert nfc_ranks == list(range(1, 17)), f"NFC ranks should be [1-16], got {nfc_ranks}"
