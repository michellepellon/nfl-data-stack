"""
Unit Tests for ESPN Score Collection

Tests the collect_espn_scores.py script which is a single point of failure
for real-time data collection.
"""

import pytest
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from collect_espn_scores import parse_espn_games, fetch_espn_scoreboard


@pytest.fixture
def mock_espn_api_response():
    """Mock ESPN API response with sample game data"""
    return {
        "events": [
            {
                "id": "401671793",
                "name": "Buffalo Bills at Kansas City Chiefs",
                "status": {
                    "type": {
                        "name": "STATUS_FINAL",
                        "state": "post",
                    }
                },
                "week": {"number": 11},
                "date": "2024-11-17T18:00:00Z",
                "competitions": [
                    {
                        "competitors": [
                            {  # Home team (index 0)
                                "team": {
                                    "displayName": "Kansas City Chiefs",
                                    "abbreviation": "KC",
                                },
                                "homeAway": "home",
                                "score": "24",
                            },
                            {  # Away team (index 1)
                                "team": {
                                    "displayName": "Buffalo Bills",
                                    "abbreviation": "BUF",
                                },
                                "homeAway": "away",
                                "score": "21",
                            },
                        ]
                    }
                ],
            },
            {  # In-progress game (should be filtered out)
                "id": "401671794",
                "name": "Miami Dolphins at New England Patriots",
                "status": {
                    "type": {
                        "name": "STATUS_IN_PROGRESS",
                        "state": "in",
                    }
                },
                "week": {"number": 11},
                "date": "2024-11-17T18:00:00Z",
                "competitions": [
                    {
                        "competitors": [
                            {"team": {"displayName": "New England Patriots"}, "score": "10"},
                            {"team": {"displayName": "Miami Dolphins"}, "score": "14"},
                        ]
                    }
                ],
            },
        ]
    }


@pytest.mark.unit
class TestEspnApiParsing:
    """Test ESPN API response parsing logic"""

    def test_parse_completed_games_only(self, mock_espn_api_response):
        """Only parse games with STATUS_FINAL and state=post"""
        games = parse_espn_games(mock_espn_api_response)

        # Should only have 1 game (completed), not 2
        assert len(games) == 1

    def test_parse_game_teams(self, mock_espn_api_response):
        """Parse home and away teams correctly"""
        games = parse_espn_games(mock_espn_api_response)
        game = games[0]

        # Home team (KC) won, so KC is winner, Bills is loser
        assert game["Winner/tie"] == "Kansas City Chiefs"
        assert game["Loser/tie"] == "Buffalo Bills"
        # @ symbol should be empty since home team won
        assert game["@"] == ""

    def test_parse_game_scores(self, mock_espn_api_response):
        """Parse game scores correctly"""
        games = parse_espn_games(mock_espn_api_response)
        game = games[0]

        assert game["PtsW"] == 24
        assert game["PtsL"] == 21

    def test_parse_week_number(self, mock_espn_api_response):
        """Parse week number correctly"""
        games = parse_espn_games(mock_espn_api_response)
        game = games[0]

        assert game["Week"] == 11

    def test_parse_winning_team(self, mock_espn_api_response):
        """Determine winning team correctly"""
        games = parse_espn_games(mock_espn_api_response)
        game = games[0]

        # Chiefs 24, Bills 21 → Chiefs win
        assert game["Winner/tie"] == "Kansas City Chiefs"

    def test_parse_empty_response(self):
        """Handle empty API response gracefully"""
        empty_response = {"events": []}
        games = parse_espn_games(empty_response)

        assert games == []

    def test_parse_missing_events_key(self):
        """Handle missing 'events' key gracefully"""
        bad_response = {}
        games = parse_espn_games(bad_response)

        assert games == []


@pytest.mark.unit
class TestEspnScoreEdgeCases:
    """Test edge cases in score parsing"""

    def test_parse_tie_game(self):
        """Handle tie games (rare in NFL, but possible)"""
        tie_game_response = {
            "events": [
                {
                    "id": "123456",
                    "status": {"type": {"name": "STATUS_FINAL", "state": "post"}},
                    "week": {"number": 10},
                    "date": "2024-11-10T18:00:00Z",
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"displayName": "Team A"}, "score": "20"},
                                {"team": {"displayName": "Team B"}, "score": "20"},
                            ]
                        }
                    ],
                }
            ]
        }

        games = parse_espn_games(tie_game_response)
        game = games[0]

        # In a tie (20-20), the implementation assigns first team as "winner"
        assert game["PtsW"] == 20
        assert game["PtsL"] == 20

    def test_parse_blowout(self):
        """Handle blowout games (large score differential)"""
        blowout_response = {
            "events": [
                {
                    "id": "123457",
                    "status": {"type": {"name": "STATUS_FINAL", "state": "post"}},
                    "week": {"number": 10},
                    "date": "2024-11-10T18:00:00Z",
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"displayName": "Strong Team"}, "score": "48"},
                                {"team": {"displayName": "Weak Team"}, "score": "3"},
                            ]
                        }
                    ],
                }
            ]
        }

        games = parse_espn_games(blowout_response)
        game = games[0]

        assert game["PtsW"] == 48
        assert game["PtsL"] == 3
        assert game["Winner/tie"] == "Strong Team"


@pytest.mark.unit
class TestEspnApiIntegration:
    """Integration tests for ESPN API calls"""

    @pytest.mark.skip(reason="Requires live ESPN API access")
    def test_fetch_espn_scoreboard_live(self):
        """Test actual ESPN API call (requires network)"""
        data = fetch_espn_scoreboard(year=2024, season_type=2)

        assert data is not None
        assert "events" in data

    def test_fetch_espn_scoreboard_timeout(self):
        """Test API timeout handling"""
        # This would require mocking requests.get to simulate timeout
        pytest.skip("Requires request mocking")

    def test_fetch_espn_scoreboard_error(self):
        """Test API error handling"""
        # This would require mocking requests.get to simulate HTTP error
        pytest.skip("Requires request mocking")


@pytest.mark.unit
class TestDataQualityChecks:
    """Test data quality validation"""

    def test_required_fields_present(self, mock_espn_api_response):
        """All required fields should be present"""
        games = parse_espn_games(mock_espn_api_response)
        game = games[0]

        required_fields = ['Week', 'Day', 'Date', 'Time', 'Winner/tie', '@', 'Loser/tie', 'PtsW', 'PtsL', 'Season']
        for field in required_fields:
            assert field in game, f"Required field '{field}' missing"

    def test_scores_are_integers(self, mock_espn_api_response):
        """Scores should be integers"""
        games = parse_espn_games(mock_espn_api_response)
        game = games[0]

        assert isinstance(game["PtsW"], int)
        assert isinstance(game["PtsL"], int)

    def test_week_number_valid_range(self, mock_espn_api_response):
        """Week numbers should be 1-18 for regular season"""
        games = parse_espn_games(mock_espn_api_response)
        game = games[0]

        assert 1 <= game["Week"] <= 18

    def test_team_names_not_empty(self, mock_espn_api_response):
        """Team names should not be empty"""
        games = parse_espn_games(mock_espn_api_response)
        game = games[0]

        assert game["Winner/tie"] != ""
        assert game["Loser/tie"] != ""
        assert len(game["Winner/tie"]) > 0
        assert len(game["Loser/tie"]) > 0
