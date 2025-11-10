"""
Official 2020 NFL Playoff Seeding Results

Source: Pro Football Reference (Week 17, 2020 season)
Used for regression testing of tiebreaker logic.
"""

# 2020 NFL Playoff Seeds (final)
NFL_2020_PLAYOFF_SEEDS = {
    "AFC": {
        1: {"team": "Kansas City Chiefs", "record": "14-2", "division": "AFC West"},
        2: {"team": "Buffalo Bills", "record": "13-3", "division": "AFC East"},
        3: {"team": "Pittsburgh Steelers", "record": "12-4", "division": "AFC North"},
        4: {"team": "Tennessee Titans", "record": "11-5", "division": "AFC South"},
        5: {"team": "Baltimore Ravens", "record": "11-5", "division": "AFC North"},
        6: {"team": "Cleveland Browns", "record": "11-5", "division": "AFC North"},
        7: {"team": "Indianapolis Colts", "record": "11-5", "division": "AFC South"},
    },
    "NFC": {
        1: {"team": "Green Bay Packers", "record": "13-3", "division": "NFC North"},
        2: {"team": "New Orleans Saints", "record": "12-4", "division": "NFC South"},
        3: {"team": "Seattle Seahawks", "record": "12-4", "division": "NFC West"},
        4: {"team": "Washington Football Team", "record": "7-9", "division": "NFC East"},
        5: {"team": "Tampa Bay Buccaneers", "record": "11-5", "division": "NFC South"},
        6: {"team": "Los Angeles Rams", "record": "10-6", "division": "NFC West"},
        7: {"team": "Chicago Bears", "record": "8-8", "division": "NFC North"},
    },
}

# Notable tiebreaker scenarios in 2020
NFL_2020_TIEBREAKER_NOTES = {
    "AFC_11-5_tie": {
        "teams": ["Tennessee Titans", "Baltimore Ravens", "Cleveland Browns", "Indianapolis Colts"],
        "note": "Four teams at 11-5. Titans won AFC South (division winner rank 4). "
        "Ravens, Browns, Colts were wild cards (seeds 5, 6, 7).",
    },
    "NFC_weak_division": {
        "teams": ["Washington Football Team"],
        "note": "Washington won NFC East with just 7-9 record (weakest division winner in NFL history with 17-game season). "
        "Made playoffs as seed 4 despite losing record.",
    },
}


def get_expected_seed(team_name: str, conference: str) -> int:
    """
    Get expected playoff seed for a team (1-7 for playoff teams).

    Args:
        team_name: Full team name (e.g., "Kansas City Chiefs")
        conference: "AFC" or "NFC"

    Returns:
        Seed number (1-7 for playoff)
        Returns None if team not found
    """
    for seed, data in NFL_2020_PLAYOFF_SEEDS[conference].items():
        if data["team"] == team_name:
            return seed
    return None


def get_playoff_teams(conference: str) -> list[str]:
    """Get list of teams that made playoffs in given conference."""
    return [data["team"] for data in NFL_2020_PLAYOFF_SEEDS[conference].values()]


def get_division_winners(conference: str) -> list[str]:
    """Get list of division winners (seeds 1-4) in given conference."""
    return [
        data["team"]
        for seed, data in NFL_2020_PLAYOFF_SEEDS[conference].items()
        if seed <= 4
    ]


def get_wild_cards(conference: str) -> list[str]:
    """Get list of wild card teams (seeds 5-7) in given conference."""
    return [
        data["team"]
        for seed, data in NFL_2020_PLAYOFF_SEEDS[conference].items()
        if seed > 4
    ]
