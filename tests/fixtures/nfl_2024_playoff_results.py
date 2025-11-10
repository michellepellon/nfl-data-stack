"""
Official 2024 NFL Playoff Seeding Results

Source: NFL.com final standings (Week 18, 2024 season)
Used for regression testing of tiebreaker logic.
"""

# 2024 NFL Playoff Seeds (final)
NFL_2024_PLAYOFF_SEEDS = {
    "AFC": {
        1: {"team": "Kansas City Chiefs", "record": "15-2", "division": "AFC West"},
        2: {"team": "Buffalo Bills", "record": "13-4", "division": "AFC East"},
        3: {"team": "Baltimore Ravens", "record": "12-5", "division": "AFC North"},
        4: {"team": "Houston Texans", "record": "10-7", "division": "AFC South"},
        5: {"team": "Los Angeles Chargers", "record": "11-6", "division": "AFC West"},
        6: {"team": "Pittsburgh Steelers", "record": "10-7", "division": "AFC North"},
        7: {"team": "Denver Broncos", "record": "10-7", "division": "AFC West"},
    },
    "NFC": {
        1: {"team": "Detroit Lions", "record": "15-2", "division": "NFC North"},
        2: {"team": "Philadelphia Eagles", "record": "14-3", "division": "NFC East"},
        3: {"team": "Los Angeles Rams", "record": "10-7", "division": "NFC West"},
        4: {"team": "Tampa Bay Buccaneers", "record": "10-7", "division": "NFC South"},
        5: {"team": "Minnesota Vikings", "record": "14-3", "division": "NFC North"},
        6: {"team": "Washington Commanders", "record": "12-5", "division": "NFC East"},
        7: {"team": "Green Bay Packers", "record": "11-6", "division": "NFC North"},
    },
}

# Teams that missed playoffs (for testing non-playoff rankings)
NFL_2024_MISSED_PLAYOFFS = {
    "AFC": [
        "Miami Dolphins",  # 8-9
        "Cincinnati Bengals",  # 9-8
        "Indianapolis Colts",  # 8-9
        "New York Jets",  # 5-12
        "Cleveland Browns",  # 3-14
        "Tennessee Titans",  # 3-14
        "New England Patriots",  # 4-13
        "Jacksonville Jaguars",  # 4-13
        "Las Vegas Raiders",  # 4-13
    ],
    "NFC": [
        "Seattle Seahawks",  # 10-7 (missed on tiebreaker!)
        "Atlanta Falcons",  # 8-9
        "Arizona Cardinals",  # 8-9
        "San Francisco 49ers",  # 6-11
        "Dallas Cowboys",  # 7-10
        "New Orleans Saints",  # 5-12
        "Chicago Bears",  # 5-12
        "Carolina Panthers",  # 5-12
        "New York Giants",  # 3-14
    ],
}

# Notable tiebreaker scenarios in 2024
NFL_2024_TIEBREAKER_NOTES = {
    "AFC_10-7_tie": {
        "teams": ["Houston Texans", "Pittsburgh Steelers", "Denver Broncos"],
        "note": "Three teams at 10-7. Texans won AFC South (division winner rank 4). "
        "Steelers and Broncos both wild cards (seeds 6 and 7).",
    },
    "NFC_10-7_tie": {
        "teams": ["Los Angeles Rams", "Tampa Bay Buccaneers", "Seattle Seahawks"],
        "note": "Three teams at 10-7. Rams won NFC West (rank 3), Bucs won NFC South (rank 4). "
        "Seahawks MISSED playoffs despite 10-7 record (tiebreaker loss to Rams for division).",
    },
    "NFC_14-3_tie": {
        "teams": ["Philadelphia Eagles", "Minnesota Vikings"],
        "note": "Both 14-3. Eagles won NFC East (seed 2), Vikings as wild card (seed 5). "
        "Eagles had better conference record.",
    },
}


def get_expected_seed(team_name: str, conference: str) -> int:
    """
    Get expected playoff seed for a team (1-7 for playoff teams, 8-16 for non-playoff).

    Args:
        team_name: Full team name (e.g., "Kansas City Chiefs")
        conference: "AFC" or "NFC"

    Returns:
        Seed number (1-7 for playoff, 8+ for non-playoff)
        Returns None if team not found
    """
    # Check playoff seeds
    for seed, data in NFL_2024_PLAYOFF_SEEDS[conference].items():
        if data["team"] == team_name:
            return seed

    # Check non-playoff teams
    if team_name in NFL_2024_MISSED_PLAYOFFS[conference]:
        # Non-playoff teams get seeds 8-16 (we don't have exact ordering)
        return 8 + NFL_2024_MISSED_PLAYOFFS[conference].index(team_name)

    return None


def get_playoff_teams(conference: str) -> list[str]:
    """Get list of teams that made playoffs in given conference."""
    return [data["team"] for data in NFL_2024_PLAYOFF_SEEDS[conference].values()]


def get_division_winners(conference: str) -> list[str]:
    """Get list of division winners (seeds 1-4) in given conference."""
    return [
        data["team"]
        for seed, data in NFL_2024_PLAYOFF_SEEDS[conference].items()
        if seed <= 4
    ]


def get_wild_cards(conference: str) -> list[str]:
    """Get list of wild card teams (seeds 5-7) in given conference."""
    return [
        data["team"]
        for seed, data in NFL_2024_PLAYOFF_SEEDS[conference].items()
        if seed > 4
    ]
