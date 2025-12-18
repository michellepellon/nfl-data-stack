#!/usr/bin/env python3
"""
Collect Vegas Lines Snapshot for CLV Tracking

Captures Vegas lines at specific points in time for Closing Line Value (CLV) analysis.
This script appends to a historical file rather than overwriting, building a time series
of line movements.

Snapshot Types:
- opening: Capture early-week lines (run Monday/Tuesday)
- closing: Capture pre-game lines (run 1-2 hours before games)
- interim: Any other point for line movement analysis

Usage:
    python scripts/collect_vegas_lines_snapshot.py opening
    python scripts/collect_vegas_lines_snapshot.py closing
    python scripts/collect_vegas_lines_snapshot.py interim

Output:
    data/nfl/vegas_lines_history.parquet (appended to existing)
"""

import argparse
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

VALID_SNAPSHOT_TYPES = ['opening', 'closing', 'interim']


def convert_american_odds_to_prob(odds: int) -> float:
    """Convert American odds to implied probability."""
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    else:
        return 100 / (odds + 100)


def convert_spread_to_prob(spread: float) -> float:
    """Convert point spread to win probability using logistic curve."""
    import math
    sigma = 13.5  # NFL empirical standard deviation
    return 1.0 / (1.0 + math.exp(-spread / sigma))


def normalize_team_name(name: str) -> str:
    """Normalize team names from The Odds API to match our database format."""
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


def fetch_nfl_odds():
    """Fetch NFL odds from The Odds API."""
    url = f"{BASE_URL}/sports/{SPORT}/odds/"

    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h,spreads",
        "oddsFormat": "american",
    }

    print(f"Fetching NFL odds from The Odds API...")

    response = requests.get(url, params=params)

    remaining = response.headers.get('x-requests-remaining')
    used = response.headers.get('x-requests-used')
    print(f"API Quota: {used} used, {remaining} remaining")

    if response.status_code != 200:
        raise Exception(f"API request failed: {response.status_code} - {response.text}")

    games = response.json()
    print(f"Fetched {len(games)} games with odds\n")

    return games


def parse_odds_response(games: list, snapshot_type: str) -> pl.DataFrame:
    """Parse The Odds API response into a structured DataFrame with snapshot metadata."""
    records = []
    snapshot_time = datetime.now(timezone.utc)

    for game in games:
        game_id = game['id']
        commence_time = game['commence_time']
        home_team = normalize_team_name(game['home_team'])
        away_team = normalize_team_name(game['away_team'])

        bookmakers = game.get('bookmakers', [])

        if not bookmakers:
            print(f"Warning: No bookmakers for {away_team} @ {home_team}")
            continue

        bookmaker = bookmakers[0]
        bookmaker_name = bookmaker['key']

        markets = {m['key']: m for m in bookmaker.get('markets', [])}

        # Get moneyline
        home_moneyline = None
        away_moneyline = None
        home_win_prob_moneyline = None

        if 'h2h' in markets:
            outcomes = {o['name']: o['price'] for o in markets['h2h']['outcomes']}
            home_moneyline = outcomes.get(game['home_team'])
            away_moneyline = outcomes.get(game['away_team'])

            if home_moneyline:
                home_win_prob_moneyline = convert_american_odds_to_prob(home_moneyline)

        # Get spread
        home_spread = None
        away_spread = None
        home_win_prob_spread = None

        if 'spreads' in markets:
            outcomes = {o['name']: o['point'] for o in markets['spreads']['outcomes']}
            home_spread = outcomes.get(game['home_team'])
            away_spread = outcomes.get(game['away_team'])

            if home_spread is not None:
                home_win_prob_spread = convert_spread_to_prob(home_spread)

        # Calculate consensus
        if home_win_prob_moneyline and home_win_prob_spread:
            home_win_prob_consensus = (home_win_prob_moneyline + home_win_prob_spread) / 2
        elif home_win_prob_moneyline:
            home_win_prob_consensus = home_win_prob_moneyline
        elif home_win_prob_spread:
            home_win_prob_consensus = home_win_prob_spread
        else:
            home_win_prob_consensus = None

        records.append({
            'api_game_id': game_id,
            'commence_time': commence_time,
            'home_team': home_team,
            'away_team': away_team,
            'bookmaker': bookmaker_name,
            'snapshot_type': snapshot_type,
            'snapshot_time': snapshot_time.isoformat(),
            'home_moneyline': home_moneyline,
            'away_moneyline': away_moneyline,
            'home_spread': home_spread,
            'away_spread': away_spread,
            'home_win_prob_moneyline': home_win_prob_moneyline,
            'home_win_prob_spread': home_win_prob_spread,
            'home_win_prob_consensus': home_win_prob_consensus,
        })

    if not records:
        print("Warning: No odds data parsed from API response")
        return pl.DataFrame()

    return pl.DataFrame(records)


def append_to_history(new_df: pl.DataFrame, history_file: Path) -> pl.DataFrame:
    """Append new snapshot to history file, avoiding duplicates."""
    if history_file.exists():
        existing_df = pl.read_parquet(history_file)
        print(f"Existing history: {len(existing_df)} records")

        # Create a dedup key: game_id + snapshot_type + snapshot_time (to the minute)
        # This prevents duplicate entries if script is run twice quickly
        new_df = new_df.with_columns([
            (pl.col('api_game_id') + '_' + pl.col('snapshot_type') + '_' +
             pl.col('snapshot_time').str.slice(0, 16)).alias('dedup_key')
        ])

        existing_df = existing_df.with_columns([
            (pl.col('api_game_id') + '_' + pl.col('snapshot_type') + '_' +
             pl.col('snapshot_time').str.slice(0, 16)).alias('dedup_key')
        ])

        # Filter out duplicates
        existing_keys = set(existing_df['dedup_key'].to_list())
        new_df = new_df.filter(~pl.col('dedup_key').is_in(existing_keys))

        if len(new_df) == 0:
            print("No new records to add (all duplicates)")
            return existing_df.drop('dedup_key')

        # Combine and drop dedup key
        combined_df = pl.concat([
            existing_df.drop('dedup_key'),
            new_df.drop('dedup_key')
        ])

        print(f"Added {len(new_df)} new records")
        return combined_df
    else:
        print("Creating new history file")
        return new_df


def main():
    parser = argparse.ArgumentParser(
        description="Collect Vegas lines snapshot for CLV tracking"
    )
    parser.add_argument(
        'snapshot_type',
        choices=VALID_SNAPSHOT_TYPES,
        help="Type of snapshot: 'opening' (early week), 'closing' (pre-game), or 'interim'"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Fetch and display data without saving"
    )

    args = parser.parse_args()

    output_dir = Path(__file__).parent.parent / "data" / "nfl"
    output_dir.mkdir(parents=True, exist_ok=True)
    history_file = output_dir / "vegas_lines_history.parquet"

    print("=" * 80)
    print(f"Collecting Vegas Lines Snapshot: {args.snapshot_type.upper()}")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)

    try:
        games = fetch_nfl_odds()

        if not games:
            print("\nNo games found. This could mean:")
            print("  - NFL season hasn't started yet")
            print("  - All games for this week are completed")
            return

        df = parse_odds_response(games, args.snapshot_type)

        if df.is_empty():
            print("Warning: No valid odds data after parsing")
            return

        # Display sample
        print("\n" + "-" * 80)
        print("Sample Data")
        print("-" * 80)
        sample = df.head(3)
        for row in sample.iter_rows(named=True):
            print(f"  {row['away_team']} @ {row['home_team']}")
            print(f"    Spread: {row['home_spread']:+.1f}, ML: {row['home_moneyline']:+d}")
            print(f"    Prob: {row['home_win_prob_consensus']:.1%}")

        if args.dry_run:
            print("\n[DRY RUN] Would save to:", history_file)
            return

        # Append to history
        combined_df = append_to_history(df, history_file)
        combined_df.write_parquet(history_file)

        print(f"\n{'=' * 80}")
        print(f"✓ Saved to {history_file}")
        print(f"  Total records in history: {len(combined_df)}")
        print(f"  Snapshot types: {combined_df['snapshot_type'].unique().to_list()}")

        # Show snapshot summary
        summary = combined_df.group_by('snapshot_type').agg(pl.count().alias('count'))
        print(f"\nSnapshot breakdown:")
        for row in summary.iter_rows(named=True):
            print(f"  {row['snapshot_type']}: {row['count']} records")

    except Exception as e:
        print(f"\n✗ Error collecting Vegas lines: {e}")
        raise


if __name__ == '__main__':
    main()
