#!/usr/bin/env python3
"""Collect travel distance and prime time adjustments for NFL games.

This script enhances the schedule data with:
- Travel distance: Great circle distance between team's home stadium and game location
- Altitude adjustment: High-altitude stadiums (primarily Denver) impact visiting teams
- Prime time classification: Thursday/Sunday/Monday night games

The collected data is exported to CSV for dbt ingestion.

Example:
    Collect features for 2020-2024 seasons:
        $ python scripts/collect_travel_and_primetime.py --start 2020 --end 2024

    Collect for specific seasons:
        $ python scripts/collect_travel_and_primetime.py --seasons 2022 2023 2024
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import nflreadpy as nfl
import polars as pl
from geopy.distance import geodesic


# NFL team abbreviations to stadium_id mapping
TEAM_TO_STADIUM = {
    'ARI': 'PHO00',
    'ATL': 'ATL97',
    'BAL': 'BAL00',
    'BUF': 'BUF00',
    'CAR': 'CAR00',
    'CHI': 'CHI98',
    'CIN': 'CIN00',
    'CLE': 'CLE00',
    'DAL': 'DAL00',
    'DEN': 'DEN00',
    'DET': 'DET00',
    'GB': 'GNB00',
    'HOU': 'HOU00',
    'IND': 'IND00',
    'JAX': 'JAX00',
    'KC': 'KAN00',
    'LA': 'LAX01',      # Rams
    'LAC': 'LAX01',     # Chargers (same stadium)
    'LV': 'VEG00',
    'MIA': 'MIA00',
    'MIN': 'MIN01',
    'NE': 'BOS00',
    'NO': 'NOR00',
    'NYG': 'NYC01',
    'NYJ': 'NYC01',
    'PHI': 'PHI00',
    'PIT': 'PIT00',
    'SEA': 'SEA00',
    'SF': 'SFO01',
    'TB': 'TAM00',
    'TEN': 'NAS00',
    'WAS': 'WAS00',
}

# Prime time adjustment values (ELO points)
PRIMETIME_ADJUSTMENTS = {
    'thursday_night': -5,      # Short rest, disadvantages road team
    'sunday_night': 0,         # No adjustment (both teams prepared)
    'monday_night': 0,         # No adjustment
    'sunday_afternoon': 0,     # Baseline
    'other': 0,                # Saturday, international games, etc.
}

# Altitude adjustment (only meaningful for Denver)
ALTITUDE_THRESHOLD = 4000  # feet
ALTITUDE_ADJUSTMENT = -10  # ELO points for visiting teams


def classify_game_time(weekday: str, gametime: str | None) -> str:
    """Classify game as prime time or regular time slot.

    Args:
        weekday: Day of week (e.g., 'Thursday', 'Sunday')
        gametime: Game time in HH:MM format (24-hour, ET)

    Returns:
        Game time classification.
    """
    if gametime is None:
        return 'other'

    try:
        hour = int(gametime.split(':')[0])
    except (ValueError, IndexError):
        return 'other'

    # Thursday Night Football
    if weekday == 'Thursday':
        return 'thursday_night'

    # Monday Night Football
    if weekday == 'Monday':
        return 'monday_night'

    # Sunday Night Football (typically 8:20 PM ET)
    if weekday == 'Sunday' and hour >= 20:
        return 'sunday_night'

    # Sunday afternoon (1 PM or 4 PM ET slots)
    if weekday == 'Sunday' and 13 <= hour < 20:
        return 'sunday_afternoon'

    # Everything else (Saturday, international, etc.)
    return 'other'


def calculate_travel_distance(
    away_lat: float,
    away_lon: float,
    game_lat: float,
    game_lon: float
) -> float:
    """Calculate great circle distance in miles.

    Args:
        away_lat: Away team's home stadium latitude
        away_lon: Away team's home stadium longitude
        game_lat: Game location latitude
        game_lon: Game location longitude

    Returns:
        Distance in miles.
    """
    away_coords = (away_lat, away_lon)
    game_coords = (game_lat, game_lon)
    return geodesic(away_coords, game_coords).miles


def main(seasons: list[int]) -> None:
    """Collect travel and prime time features for specified seasons.

    Args:
        seasons: List of seasons to process (e.g., [2020, 2021, 2022])
    """
    # Set up paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    data_dir = project_root / 'data' / 'nfl'

    # Load stadium reference data
    print("Loading stadium data...")
    stadiums = pl.read_csv(data_dir / 'nfl_stadiums.csv')
    print(f"Loaded {len(stadiums)} stadiums")

    # Load schedules
    print(f"\nLoading schedules for seasons: {seasons}")
    schedules = nfl.load_schedules(seasons)
    print(f"Loaded {len(schedules)} games")

    # Filter to regular season only
    schedules = schedules.filter(pl.col('game_type') == 'REG')
    print(f"Regular season games: {len(schedules)}")

    # Join game location stadium data
    schedules = schedules.join(
        stadiums.select(['stadium_id', 'latitude', 'longitude', 'altitude_ft']),
        on='stadium_id',
        how='left'
    ).rename({
        'latitude': 'game_latitude',
        'longitude': 'game_longitude',
        'altitude_ft': 'game_altitude'
    })

    # Join away team home stadium data
    schedules = schedules.with_columns([
        pl.col('away_team').replace(TEAM_TO_STADIUM).alias('away_stadium_id')
    ])

    schedules = schedules.join(
        stadiums.select(['stadium_id', 'latitude', 'longitude']),
        left_on='away_stadium_id',
        right_on='stadium_id',
        how='left'
    ).rename({
        'latitude': 'away_home_latitude',
        'longitude': 'away_home_longitude'
    })

    # Calculate travel distance for away team
    print("\nCalculating travel distances...")
    schedules = schedules.with_columns([
        pl.struct(['away_home_latitude', 'away_home_longitude', 'game_latitude', 'game_longitude'])
        .map_elements(
            lambda x: calculate_travel_distance(
                x['away_home_latitude'],
                x['away_home_longitude'],
                x['game_latitude'],
                x['game_longitude']
            ) if all(v is not None for v in x.values()) else None,
            return_dtype=pl.Float64
        )
        .alias('travel_distance_miles')
    ])

    # Calculate travel adjustment (-4 ELO per 1,000 miles)
    schedules = schedules.with_columns([
        (pl.col('travel_distance_miles') / 1000 * -4)
        .fill_null(0)
        .alias('travel_adjustment')
    ])

    # Calculate altitude adjustment (visiting team only)
    schedules = schedules.with_columns([
        pl.when(pl.col('game_altitude') > ALTITUDE_THRESHOLD)
        .then(ALTITUDE_ADJUSTMENT)
        .otherwise(0)
        .alias('altitude_adjustment')
    ])

    # Classify prime time games
    print("Classifying prime time games...")
    schedules = schedules.with_columns([
        pl.struct(['weekday', 'gametime'])
        .map_elements(
            lambda x: classify_game_time(x['weekday'], x['gametime']),
            return_dtype=pl.Utf8
        )
        .alias('game_time_slot')
    ])

    # Add prime time adjustment
    schedules = schedules.with_columns([
        pl.col('game_time_slot')
        .replace(PRIMETIME_ADJUSTMENTS, default=0)
        .alias('primetime_adjustment')
    ])

    # Calculate total contextual adjustment
    schedules = schedules.with_columns([
        (
            pl.col('travel_adjustment') +
            pl.col('altitude_adjustment') +
            pl.col('primetime_adjustment')
        ).alias('total_contextual_adjustment')
    ])

    # Select output columns
    output = schedules.select([
        'game_id',
        'season',
        'week',
        'home_team',
        'away_team',
        'weekday',
        'gametime',
        'game_time_slot',
        'travel_distance_miles',
        'game_altitude',
        'travel_adjustment',
        'altitude_adjustment',
        'primetime_adjustment',
        'total_contextual_adjustment'
    ])

    # Export to CSV
    output_path = data_dir / 'nfl_travel_primetime.csv'
    output.write_csv(output_path)
    print(f"\n✓ Exported {len(output)} games to {output_path}")

    # Print summary statistics
    print("\nSummary Statistics:")
    print(f"  Average travel distance: {output['travel_distance_miles'].mean():.0f} miles")
    print(f"  Max travel distance: {output['travel_distance_miles'].max():.0f} miles")
    print(f"  High altitude games: {(output['game_altitude'] > ALTITUDE_THRESHOLD).sum()}")
    print(f"  Thursday night games: {(output['game_time_slot'] == 'thursday_night').sum()}")
    print(f"  Sunday night games: {(output['game_time_slot'] == 'sunday_night').sum()}")
    print(f"  Monday night games: {(output['game_time_slot'] == 'monday_night').sum()}")
    print(f"  Average total adjustment: {output['total_contextual_adjustment'].mean():.2f} ELO")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Collect travel distance and prime time features for NFL games'
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--seasons',
        type=int,
        nargs='+',
        help='Specific seasons to collect (e.g., --seasons 2022 2023 2024)'
    )
    group.add_argument(
        '--start',
        type=int,
        help='Start season (inclusive, use with --end)'
    )

    parser.add_argument(
        '--end',
        type=int,
        help='End season (inclusive, use with --start)'
    )

    args = parser.parse_args()

    if args.seasons:
        seasons = args.seasons
    elif args.start and args.end:
        seasons = list(range(args.start, args.end + 1))
    else:
        parser.error('Must specify either --seasons or both --start and --end')

    main(seasons)
