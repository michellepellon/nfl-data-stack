#!/usr/bin/env python3
"""
Collect Vegas Lines from The Odds API

Fetches NFL spreads and moneylines for the 2025 season and converts them to
implied win probabilities for ensemble prediction.

API Documentation: https://the-odds-api.com/liveapi/guides/v4/

Usage:
    python scripts/collect_vegas_lines.py
"""

import requests
import pandas as pd
import polars as pl
from pathlib import Path
from datetime import datetime, timezone
import json


# The Odds API Configuration
API_KEY = "80a638ad41d589e0acbbeed909e3bae1"
BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"


def convert_american_odds_to_prob(odds: int) -> float:
    """
    Convert American odds to implied probability.

    American odds format:
    - Negative (e.g., -150): Favorite, need to bet $150 to win $100
    - Positive (e.g., +130): Underdog, bet $100 to win $130

    Formula:
    - Negative: probability = |odds| / (|odds| + 100)
    - Positive: probability = 100 / (odds + 100)

    Args:
        odds: American odds (e.g., -150, +130)

    Returns:
        Implied probability (0.0 to 1.0)
    """
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    else:
        return 100 / (odds + 100)


def convert_spread_to_prob(spread: float, total: float = 45.0) -> float:
    """
    Convert point spread to win probability using empirical NFL data.

    Based on historical NFL data, the relationship between spread and win probability
    follows a logistic curve. A common approximation:

    P(home wins) = 1 / (1 + exp(-spread / sigma))

    Where sigma ≈ 13.5 for NFL (empirically derived from historical data).

    Args:
        spread: Point spread from home team's perspective (positive = home favored)
        total: Expected total points (used for context, default 45)

    Returns:
        Home team win probability (0.0 to 1.0)
    """
    import math
    sigma = 13.5  # NFL empirical standard deviation
    return 1.0 / (1.0 + math.exp(-spread / sigma))


def normalize_team_name(name: str) -> str:
    """
    Normalize team names from The Odds API to match our database format.

    The Odds API uses city names (e.g., "Buffalo Bills")
    Our DB uses full names (e.g., "Buffalo Bills")

    This function handles any discrepancies.
    """
    # The Odds API format matches our format, but we'll handle edge cases
    team_mapping = {
        "Arizona Cardinals": "Arizona Cardinals",
        "Atlanta Falcons": "Atlanta Falcons",
        "Baltimore Ravens": "Baltimore Ravens",
        "Buffalo Bills": "Buffalo Bills",
        "Carolina Panthers": "Carolina Panthers",
        "Chicago Bears": "Chicago Bears",
        "Cincinnati Bengals": "Cincinnati Bengals",
        "Cleveland Browns": "Cleveland Browns",
        "Dallas Cowboys": "Dallas Cowboys",
        "Denver Broncos": "Denver Broncos",
        "Detroit Lions": "Detroit Lions",
        "Green Bay Packers": "Green Bay Packers",
        "Houston Texans": "Houston Texans",
        "Indianapolis Colts": "Indianapolis Colts",
        "Jacksonville Jaguars": "Jacksonville Jaguars",
        "Kansas City Chiefs": "Kansas City Chiefs",
        "Las Vegas Raiders": "Las Vegas Raiders",
        "Los Angeles Chargers": "Los Angeles Chargers",
        "Los Angeles Rams": "Los Angeles Rams",
        "Miami Dolphins": "Miami Dolphins",
        "Minnesota Vikings": "Minnesota Vikings",
        "New England Patriots": "New England Patriots",
        "New Orleans Saints": "New Orleans Saints",
        "New York Giants": "New York Giants",
        "New York Jets": "New York Jets",
        "Philadelphia Eagles": "Philadelphia Eagles",
        "Pittsburgh Steelers": "Pittsburgh Steelers",
        "San Francisco 49ers": "San Francisco 49ers",
        "Seattle Seahawks": "Seattle Seahawks",
        "Tampa Bay Buccaneers": "Tampa Bay Buccaneers",
        "Tennessee Titans": "Tennessee Titans",
        "Washington Commanders": "Washington Commanders",
    }

    return team_mapping.get(name, name)


def fetch_nfl_odds(commence_time_from: str = None, commence_time_to: str = None):
    """
    Fetch NFL odds from The Odds API.

    Args:
        commence_time_from: ISO 8601 datetime (e.g., "2025-09-04T00:00:00Z")
        commence_time_to: ISO 8601 datetime (e.g., "2025-12-31T23:59:59Z")

    Returns:
        List of games with odds data
    """
    url = f"{BASE_URL}/sports/{SPORT}/odds/"

    params = {
        "apiKey": API_KEY,
        "regions": "us",  # US bookmakers
        "markets": "h2h,spreads",  # Head-to-head (moneyline) and spreads
        "oddsFormat": "american",  # American odds format (-150, +130, etc.)
    }

    if commence_time_from:
        params["commenceTimeFrom"] = commence_time_from
    if commence_time_to:
        params["commenceTimeTo"] = commence_time_to

    print(f"Fetching NFL odds from The Odds API...")
    print(f"URL: {url}")
    print(f"Params: {json.dumps(params, indent=2)}")

    response = requests.get(url, params=params)

    # Check remaining API quota
    remaining = response.headers.get('x-requests-remaining')
    used = response.headers.get('x-requests-used')
    print(f"\nAPI Quota: {used} used, {remaining} remaining")

    if response.status_code != 200:
        raise Exception(f"API request failed: {response.status_code} - {response.text}")

    games = response.json()
    print(f"Fetched {len(games)} games with odds\n")

    return games


def parse_odds_response(games: list) -> pl.DataFrame:
    """
    Parse The Odds API response into a structured DataFrame.

    Args:
        games: List of game objects from The Odds API

    Returns:
        Polars DataFrame with parsed odds data
    """
    records = []

    for game in games:
        game_id = game['id']
        commence_time = game['commence_time']
        home_team = normalize_team_name(game['home_team'])
        away_team = normalize_team_name(game['away_team'])

        # Extract bookmaker odds (use consensus if multiple books)
        bookmakers = game.get('bookmakers', [])

        if not bookmakers:
            print(f"Warning: No bookmakers for {away_team} @ {home_team}")
            continue

        # Use first bookmaker (typically FanDuel, DraftKings, or consensus)
        bookmaker = bookmakers[0]
        bookmaker_name = bookmaker['key']

        # Extract markets
        markets = {m['key']: m for m in bookmaker.get('markets', [])}

        # Get moneyline (h2h)
        home_moneyline = None
        away_moneyline = None
        home_win_prob_moneyline = None
        away_win_prob_moneyline = None

        if 'h2h' in markets:
            outcomes = {o['name']: o['price'] for o in markets['h2h']['outcomes']}
            home_moneyline = outcomes.get(game['home_team'])
            away_moneyline = outcomes.get(game['away_team'])

            if home_moneyline:
                home_win_prob_moneyline = convert_american_odds_to_prob(home_moneyline)
                away_win_prob_moneyline = 1 - home_win_prob_moneyline

        # Get spread
        home_spread = None
        away_spread = None
        home_win_prob_spread = None
        away_win_prob_spread = None

        if 'spreads' in markets:
            outcomes = {o['name']: o['point'] for o in markets['spreads']['outcomes']}
            home_spread = outcomes.get(game['home_team'])
            away_spread = outcomes.get(game['away_team'])

            if home_spread is not None:
                home_win_prob_spread = convert_spread_to_prob(home_spread)
                away_win_prob_spread = 1 - home_win_prob_spread

        records.append({
            'api_game_id': game_id,
            'commence_time': commence_time,
            'home_team': home_team,
            'away_team': away_team,
            'bookmaker': bookmaker_name,
            'home_moneyline': home_moneyline,
            'away_moneyline': away_moneyline,
            'home_spread': home_spread,
            'away_spread': away_spread,
            'home_win_prob_moneyline': home_win_prob_moneyline,
            'away_win_prob_moneyline': away_win_prob_moneyline,
            'home_win_prob_spread': home_win_prob_spread,
            'away_win_prob_spread': away_win_prob_spread,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
        })

    if not records:
        print("Warning: No odds data parsed from API response")
        return pl.DataFrame()

    df = pl.DataFrame(records)

    # Calculate consensus probabilities (average of moneyline and spread)
    df = df.with_columns([
        ((pl.col('home_win_prob_moneyline') + pl.col('home_win_prob_spread')) / 2).alias('home_win_prob_consensus'),
        ((pl.col('away_win_prob_moneyline') + pl.col('away_win_prob_spread')) / 2).alias('away_win_prob_consensus'),
    ])

    return df


def main():
    """Collect Vegas lines for 2025 NFL season"""

    output_dir = Path(__file__).parent.parent / "data" / "nfl"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "vegas_lines_2025.parquet"

    print("=" * 80)
    print("Collecting Vegas Lines for 2025 NFL Season")
    print("=" * 80)

    # Fetch current and upcoming games (The Odds API only provides future games)
    # For historical data, we would need to make requests during the season
    # or use a different data source

    print("\n[1/2] Fetching current and upcoming NFL games...")

    try:
        games = fetch_nfl_odds()

        if not games:
            print("\nNo games found. This could mean:")
            print("  - NFL season hasn't started yet")
            print("  - All games for this week are completed")
            print("  - API is not returning data")
            print("\nTry checking the API directly or wait until game week.")
            return

        print(f"\n[2/2] Parsing {len(games)} games...")
        df = parse_odds_response(games)

        if df.is_empty():
            print("Warning: No valid odds data after parsing")
            return

        # Save to parquet
        df.write_parquet(output_file)
        print(f"\n✓ Saved {len(df)} games to {output_file}")

        # Display summary
        print("\n" + "=" * 80)
        print("Summary")
        print("=" * 80)
        print(f"Games collected: {len(df)}")
        print(f"Bookmakers: {df['bookmaker'].unique().to_list()}")
        print(f"\nSample game:")
        if len(df) > 0:
            sample = df.head(1)
            print(f"  {sample['away_team'][0]} @ {sample['home_team'][0]}")
            print(f"  Home spread: {sample['home_spread'][0]:+.1f}")
            print(f"  Home win prob (spread): {sample['home_win_prob_spread'][0]:.1%}")
            print(f"  Home moneyline: {sample['home_moneyline'][0]:+d}")
            print(f"  Home win prob (moneyline): {sample['home_win_prob_moneyline'][0]:.1%}")
            print(f"  Consensus prob: {sample['home_win_prob_consensus'][0]:.1%}")

    except Exception as e:
        print(f"\n✗ Error collecting Vegas lines: {e}")
        raise


if __name__ == '__main__':
    main()
