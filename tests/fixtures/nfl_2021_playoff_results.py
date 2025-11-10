"""
Official 2021 NFL Playoff Seeding Results

Source: Pro Football Reference (Week 18, 2021 season)
Used for regression testing of tiebreaker logic.
"""

# 2021 NFL Playoff Seeds (final)
NFL_2021_PLAYOFF_SEEDS = {
    "AFC": {
        1: {"team": "Tennessee Titans", "record": "12-5", "division": "AFC South"},
        2: {"team": "Kansas City Chiefs", "record": "12-5", "division": "AFC West"},
        3: {"team": "Buffalo Bills", "record": "11-6", "division": "AFC East"},
        4: {"team": "Cincinnati Bengals", "record": "10-7", "division": "AFC North"},
        5: {"team": "Las Vegas Raiders", "record": "10-7", "division": "AFC West"},
        6: {"team": "New England Patriots", "record": "10-7", "division": "AFC East"},
        7: {"team": "Pittsburgh Steelers", "record": "9-7-1", "division": "AFC North"},
    },
    "NFC": {
        1: {"team": "Green Bay Packers", "record": "13-4", "division": "NFC North"},
        2: {"team": "Tampa Bay Buccaneers", "record": "13-4", "division": "NFC South"},
        3: {"team": "Dallas Cowboys", "record": "12-5", "division": "NFC East"},
        4: {"team": "Los Angeles Rams", "record": "12-5", "division": "NFC West"},
        5: {"team": "Arizona Cardinals", "record": "11-6", "division": "NFC West"},
        6: {"team": "San Francisco 49ers", "record": "10-7", "division": "NFC West"},
        7: {"team": "Philadelphia Eagles", "record": "9-8", "division": "NFC East"},
    },
}

# Notable tiebreaker scenarios in 2021
NFL_2021_TIEBREAKER_NOTES = {
    "AFC_12-5_tie": {
        "teams": ["Tennessee Titans", "Kansas City Chiefs"],
        "note": "Both 12-5. Titans won AFC South (seed 1), Chiefs won AFC West (seed 2). "
        "Titans got #1 seed due to better conference record.",
    },
    "AFC_10-7_tie": {
        "teams": ["Cincinnati Bengals", "Las Vegas Raiders", "New England Patriots"],
        "note": "Three teams at 10-7. Bengals won AFC North (division winner rank 4). "
        "Raiders and Patriots both wild cards (seeds 5 and 6).",
    },
    "NFC_13-4_tie": {
        "teams": ["Green Bay Packers", "Tampa Bay Buccaneers"],
        "note": "Both 13-4. Packers won NFC North (seed 1), Bucs won NFC South (seed 2). "
        "Packers got #1 seed due to head-to-head win.",
    },
}


def get_expected_seed(team_name: str, conference: str) -> int:
    """
    Get expected playoff seed for a team (1-7 for playoff teams).

    Args:
        team_name: Full team name (e.g., "Tennessee Titans")
        conference: "AFC" or "NFC"

    Returns:
        Seed number (1-7 for playoff)
        Returns None if team not found
    """
    for seed, data in NFL_2021_PLAYOFF_SEEDS[conference].items():
        if data["team"] == team_name:
            return seed
    return None


def get_playoff_teams(conference: str) -> list[str]:
    """Get list of teams that made playoffs in given conference."""
    return [data["team"] for data in NFL_2021_PLAYOFF_SEEDS[conference].values()]


def get_division_winners(conference: str) -> list[str]:
    """Get list of division winners (seeds 1-4) in given conference."""
    return [
        data["team"]
        for seed, data in NFL_2021_PLAYOFF_SEEDS[conference].items()
        if seed <= 4
    ]


def get_wild_cards(conference: str) -> list[str]:
    """Get list of wild card teams (seeds 5-7) in given conference."""
    return [
        data["team"]
        for seed, data in NFL_2021_PLAYOFF_SEEDS[conference].items()
        if seed > 4
    ]
