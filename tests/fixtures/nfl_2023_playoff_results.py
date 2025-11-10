"""
Official 2023 NFL Playoff Seeding Results

Source: Pro Football Reference (Week 18, 2023 season)
Used for regression testing of tiebreaker logic.
"""

# 2023 NFL Playoff Seeds (final)
NFL_2023_PLAYOFF_SEEDS = {
    "AFC": {
        1: {"team": "Baltimore Ravens", "record": "13-4", "division": "AFC North"},
        2: {"team": "Buffalo Bills", "record": "11-6", "division": "AFC East"},
        3: {"team": "Kansas City Chiefs", "record": "11-6", "division": "AFC West"},
        4: {"team": "Houston Texans", "record": "10-7", "division": "AFC South"},
        5: {"team": "Cleveland Browns", "record": "11-6", "division": "AFC North"},
        6: {"team": "Miami Dolphins", "record": "11-6", "division": "AFC East"},
        7: {"team": "Pittsburgh Steelers", "record": "10-7", "division": "AFC North"},
    },
    "NFC": {
        1: {"team": "San Francisco 49ers", "record": "12-5", "division": "NFC West"},
        2: {"team": "Dallas Cowboys", "record": "12-5", "division": "NFC East"},
        3: {"team": "Detroit Lions", "record": "12-5", "division": "NFC North"},
        4: {"team": "Tampa Bay Buccaneers", "record": "9-8", "division": "NFC South"},
        5: {"team": "Philadelphia Eagles", "record": "11-6", "division": "NFC East"},
        6: {"team": "Los Angeles Rams", "record": "10-7", "division": "NFC West"},
        7: {"team": "Green Bay Packers", "record": "9-8", "division": "NFC North"},
    },
}

# Notable tiebreaker scenarios in 2023
NFL_2023_TIEBREAKER_NOTES = {
    "AFC_11-6_tie": {
        "teams": ["Buffalo Bills", "Kansas City Chiefs", "Cleveland Browns", "Miami Dolphins"],
        "note": "Four teams at 11-6. Bills won AFC East (seed 2), Chiefs won AFC West (seed 3). "
        "Browns and Dolphins were wild cards (seeds 5 and 6).",
    },
    "NFC_12-5_tie": {
        "teams": ["San Francisco 49ers", "Dallas Cowboys", "Detroit Lions"],
        "note": "Three teams at 12-5. All division winners. "
        "49ers got #1 seed (NFC West), Cowboys #2 (NFC East), Lions #3 (NFC North). "
        "Seeding determined by conference record and strength of victory.",
    },
    "AFC_10-7_tie": {
        "teams": ["Houston Texans", "Pittsburgh Steelers"],
        "note": "Both 10-7. Texans won AFC South (division winner rank 4). "
        "Steelers was wild card (seed 7).",
    },
}


def get_expected_seed(team_name: str, conference: str) -> int:
    """
    Get expected playoff seed for a team (1-7 for playoff teams).

    Args:
        team_name: Full team name (e.g., "Baltimore Ravens")
        conference: "AFC" or "NFC"

    Returns:
        Seed number (1-7 for playoff)
        Returns None if team not found
    """
    for seed, data in NFL_2023_PLAYOFF_SEEDS[conference].items():
        if data["team"] == team_name:
            return seed
    return None


def get_playoff_teams(conference: str) -> list[str]:
    """Get list of teams that made playoffs in given conference."""
    return [data["team"] for data in NFL_2023_PLAYOFF_SEEDS[conference].values()]


def get_division_winners(conference: str) -> list[str]:
    """Get list of division winners (seeds 1-4) in given conference."""
    return [
        data["team"]
        for seed, data in NFL_2023_PLAYOFF_SEEDS[conference].items()
        if seed <= 4
    ]


def get_wild_cards(conference: str) -> list[str]:
    """Get list of wild card teams (seeds 5-7) in given conference."""
    return [
        data["team"]
        for seed, data in NFL_2023_PLAYOFF_SEEDS[conference].items()
        if seed > 4
    ]
