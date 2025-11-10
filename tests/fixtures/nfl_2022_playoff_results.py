"""
Official 2022 NFL Playoff Seeding Results

Source: Pro Football Reference (Week 18, 2022 season)
Used for regression testing of tiebreaker logic.
"""

# 2022 NFL Playoff Seeds (final)
NFL_2022_PLAYOFF_SEEDS = {
    "AFC": {
        1: {"team": "Kansas City Chiefs", "record": "14-3", "division": "AFC West"},
        2: {"team": "Buffalo Bills", "record": "13-3", "division": "AFC East"},
        3: {"team": "Cincinnati Bengals", "record": "12-4", "division": "AFC North"},
        4: {"team": "Jacksonville Jaguars", "record": "9-8", "division": "AFC South"},
        5: {"team": "Los Angeles Chargers", "record": "10-7", "division": "AFC West"},
        6: {"team": "Baltimore Ravens", "record": "10-7", "division": "AFC North"},
        7: {"team": "Miami Dolphins", "record": "9-8", "division": "AFC East"},
    },
    "NFC": {
        1: {"team": "Philadelphia Eagles", "record": "14-3", "division": "NFC East"},
        2: {"team": "San Francisco 49ers", "record": "13-4", "division": "NFC West"},
        3: {"team": "Minnesota Vikings", "record": "13-4", "division": "NFC North"},
        4: {"team": "Tampa Bay Buccaneers", "record": "8-9", "division": "NFC South"},
        5: {"team": "Dallas Cowboys", "record": "12-5", "division": "NFC East"},
        6: {"team": "New York Giants", "record": "9-7-1", "division": "NFC East"},
        7: {"team": "Seattle Seahawks", "record": "9-8", "division": "NFC West"},
    },
}

# Notable tiebreaker scenarios in 2022
NFL_2022_TIEBREAKER_NOTES = {
    "NFC_13-4_tie": {
        "teams": ["San Francisco 49ers", "Minnesota Vikings"],
        "note": "Both 13-4. 49ers won NFC West (seed 2), Vikings won NFC North (seed 3). "
        "49ers got higher seed due to head-to-head win.",
    },
    "AFC_10-7_tie": {
        "teams": ["Los Angeles Chargers", "Baltimore Ravens"],
        "note": "Both 10-7. Chargers got seed 5, Ravens seed 6. "
        "Decided by conference record tiebreaker.",
    },
    "NFC_weak_division": {
        "teams": ["Tampa Bay Buccaneers"],
        "note": "Bucs won NFC South with 8-9 losing record. "
        "Made playoffs as seed 4 despite being below .500.",
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
    for seed, data in NFL_2022_PLAYOFF_SEEDS[conference].items():
        if data["team"] == team_name:
            return seed
    return None


def get_playoff_teams(conference: str) -> list[str]:
    """Get list of teams that made playoffs in given conference."""
    return [data["team"] for data in NFL_2022_PLAYOFF_SEEDS[conference].values()]


def get_division_winners(conference: str) -> list[str]:
    """Get list of division winners (seeds 1-4) in given conference."""
    return [
        data["team"]
        for seed, data in NFL_2022_PLAYOFF_SEEDS[conference].items()
        if seed <= 4
    ]


def get_wild_cards(conference: str) -> list[str]:
    """Get list of wild card teams (seeds 5-7) in given conference."""
    return [
        data["team"]
        for seed, data in NFL_2022_PLAYOFF_SEEDS[conference].items()
        if seed > 4
    ]
