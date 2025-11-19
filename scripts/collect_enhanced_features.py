#!/usr/bin/env python3
"""Collect enhanced features (rest days, weather, injuries) for NFL games.

This script uses nflreadpy to download contextual features that impact game outcomes:
- Rest days: Days of rest before each game for both teams
- Weather: Temperature, wind speed, stadium roof type (outdoor games only)
- Injuries: Team-level injury impact scores by position group

The collected data is merged with game schedules and exported to CSV for dbt ingestion.

Example:
    Collect features for 2020-2024 seasons:
        $ python scripts/collect_enhanced_features.py --start 2020 --end 2024

    Collect for specific seasons:
        $ python scripts/collect_enhanced_features.py --seasons 2022 2023 2024
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import nflreadpy as nfl
import polars as pl

# Team name mapping (full name -> abbreviation)
TEAM_NAME_MAP = {
    'Arizona Cardinals': 'ARI',
    'Atlanta Falcons': 'ATL',
    'Baltimore Ravens': 'BAL',
    'Buffalo Bills': 'BUF',
    'Carolina Panthers': 'CAR',
    'Chicago Bears': 'CHI',
    'Cincinnati Bengals': 'CIN',
    'Cleveland Browns': 'CLE',
    'Dallas Cowboys': 'DAL',
    'Denver Broncos': 'DEN',
    'Detroit Lions': 'DET',
    'Green Bay Packers': 'GB',
    'Houston Texans': 'HOU',
    'Indianapolis Colts': 'IND',
    'Jacksonville Jaguars': 'JAX',
    'Kansas City Chiefs': 'KC',
    'Las Vegas Raiders': 'LV',
    'Los Angeles Chargers': 'LAC',
    'Los Angeles Rams': 'LA',
    'Miami Dolphins': 'MIA',
    'Minnesota Vikings': 'MIN',
    'New England Patriots': 'NE',
    'New Orleans Saints': 'NO',
    'New York Giants': 'NYG',
    'New York Jets': 'NYJ',
    'Philadelphia Eagles': 'PHI',
    'Pittsburgh Steelers': 'PIT',
    'San Francisco 49ers': 'SF',
    'Seattle Seahawks': 'SEA',
    'Tampa Bay Buccaneers': 'TB',
    'Tennessee Titans': 'TEN',
    'Washington Commanders': 'WAS',
}

# Position weights (out of 100 total impact points)
POSITION_WEIGHTS = {
    'QB': 40.0,
    'RB': 5.0,
    'WR': 5.0,
    'TE': 5.0,
    'OL': 3.0,
    'DL': 3.0,
    'LB': 3.0,
    'DB': 2.0,
    'K': 1.0,
    'P': 1.0,
    'LS': 1.0,
}

# Position group caps (max impact per group)
POSITION_CAPS = {
    'QB': 40.0,
    'RB': 5.0,
    'WR': 15.0,  # Max 3 WRs impacted
    'TE': 10.0,  # Max 2 TEs impacted
    'OL': 15.0,  # Max 5 OL impacted
    'DL': 15.0,
    'LB': 15.0,
    'DB': 10.0,
    'K': 1.0,
    'P': 1.0,
    'LS': 1.0,
}

# Injury status multipliers
STATUS_MULTIPLIERS = {
    'Out': 1.0,
    'Doubtful': 0.75,
    'Questionable': 0.5,
    'Did Not Participate In Practice': 0.75,
    'Limited Participation in Practice': 0.4,
    'Full Participation in Practice': 0.0,
}


def map_position_group(position: str) -> str:
    """Map detailed position to broad position group.

    Args:
        position: Player position code (e.g., 'QB', 'WR', 'T', 'CB')

    Returns:
        Position group for injury weighting.
    """
    position = position.upper() if position else 'UNKNOWN'

    # Quarterback
    if position in ('QB',):
        return 'QB'

    # Running backs / Fullbacks
    if position in ('RB', 'FB', 'HB'):
        return 'RB'

    # Wide receivers / Slot receivers
    if position in ('WR', 'FL', 'SE'):
        return 'WR'

    # Tight ends
    if position in ('TE',):
        return 'TE'

    # Offensive line
    if position in ('T', 'G', 'C', 'OT', 'OG', 'OL'):
        return 'OL'

    # Defensive line
    if position in ('DE', 'DT', 'NT', 'DL'):
        return 'DL'

    # Linebackers
    if position in ('LB', 'MLB', 'OLB', 'ILB'):
        return 'LB'

    # Defensive backs
    if position in ('CB', 'S', 'SS', 'FS', 'DB'):
        return 'DB'

    # Special teams
    if position in ('K', 'P', 'LS'):
        return position

    return 'UNKNOWN'


def calculate_team_injury_scores(injuries: pl.DataFrame) -> pl.DataFrame:
    """Calculate team-level injury impact scores by week.

    Args:
        injuries: DataFrame with columns: season, team, week, position,
                  report_status, etc.

    Returns:
        DataFrame with columns: season, team, week, injury_score (0-100).
    """
    # Filter to regular season injuries only
    injuries = injuries.filter(pl.col('game_type') == 'REG')

    # Add position group
    injuries = injuries.with_columns(
        pl.col('position').map_elements(
            map_position_group,
            return_dtype=pl.Utf8
        ).alias('position_group')
    )

    # Add status multiplier
    injuries = injuries.with_columns(
        pl.col('report_status').map_elements(
            lambda s: STATUS_MULTIPLIERS.get(s, 0.5),
            return_dtype=pl.Float64
        ).alias('status_multiplier')
    )

    # Calculate weighted impact per injury
    injuries = injuries.with_columns(
        pl.col('position_group').map_elements(
            lambda p: POSITION_WEIGHTS.get(p, 0.0),
            return_dtype=pl.Float64
        ).alias('position_weight')
    )

    injuries = injuries.with_columns(
        (pl.col('position_weight') * pl.col('status_multiplier')).alias('weighted_impact')
    )

    # Group by team-week and sum impacts (capped by position group)
    # This is a simplified approach - proper implementation would cap per position group
    injury_scores = (
        injuries
        .group_by(['season', 'team', 'week'])
        .agg(pl.col('weighted_impact').sum().alias('injury_score'))
    )

    # Ensure season and week are int32 to match schedules
    injury_scores = injury_scores.with_columns([
        pl.col('season').cast(pl.Int32),
        pl.col('week').cast(pl.Int32),
    ])

    # Cap injury scores at 100
    injury_scores = injury_scores.with_columns(
        pl.when(pl.col('injury_score') > 100.0)
        .then(100.0)
        .otherwise(pl.col('injury_score'))
        .alias('injury_score')
    )

    return injury_scores


def collect_enhanced_features(
    seasons: list[int],
    output_path: Path = Path('data/nfl/nfl_enhanced_features.csv'),
) -> None:
    """Collect and merge rest, weather, and injury data for NFL games.

    Args:
        seasons: List of seasons to collect data for.
        output_path: Path to save enhanced features CSV. Defaults to
                     'data/nfl/nfl_enhanced_features.csv'.

    Raises:
        FileNotFoundError: If nflreadpy data is unavailable.
        ValueError: If seasons list is empty.
    """
    if not seasons:
        raise ValueError("Seasons list cannot be empty")

    print(f"\nCollecting enhanced features for seasons: {seasons}")

    # Load schedules (has rest days, weather, stadium info)
    print("Loading schedules...")
    schedules = nfl.load_schedules(seasons)

    # Filter to regular season only
    schedules = schedules.filter(pl.col('game_type') == 'REG')

    print(f"Loaded {len(schedules)} regular season games")

    # Select relevant columns
    enhanced = schedules.select([
        'game_id',
        'season',
        'week',
        'home_team',
        'away_team',
        'home_rest',
        'away_rest',
        'roof',
        'temp',
        'wind',
        'stadium_id',
        'stadium',
    ])

    # Calculate rest differential
    enhanced = enhanced.with_columns(
        (pl.col('home_rest') - pl.col('away_rest')).alias('rest_diff')
    )

    # Merge weather forecasts for future weeks (weeks without historical data)
    print("Checking for weather forecasts...")
    data_dir = Path(__file__).parent.parent / 'data' / 'nfl'
    forecast_files = list(data_dir.glob('weather_forecasts_week*.csv'))

    if forecast_files:
        print(f"Found {len(forecast_files)} forecast files")
        for forecast_file in forecast_files:
            try:
                forecasts = pl.read_csv(forecast_file)
                print(f"  Loading {forecast_file.name}: {len(forecasts)} games")

                # Convert full team names to abbreviations
                forecasts = forecasts.with_columns(
                    pl.col('home_team').map_elements(
                        lambda name: TEAM_NAME_MAP.get(name, name),
                        return_dtype=pl.Utf8
                    ).alias('home_team'),
                    pl.col('away_team').map_elements(
                        lambda name: TEAM_NAME_MAP.get(name, name),
                        return_dtype=pl.Utf8
                    ).alias('away_team')
                )

                print(f"  Forecast teams after conversion: {sorted(forecasts['home_team'].unique().to_list())}")
                print(f"  Forecast weeks: {sorted(forecasts['week'].unique().to_list())}")

                # Merge forecasts by week and home_team (game_id formats don't match)
                # nflverse uses "2025_12_BUF_HOU", we use sequential numbers
                enhanced = enhanced.join(
                    forecasts.select(['week', 'home_team', 'temperature', 'wind_speed', 'roof']),
                    on=['week', 'home_team'],
                    how='left',
                    suffix='_forecast'
                )

                # Debug: Check how many forecasts matched
                matched = enhanced.filter(pl.col('temperature').is_not_null())
                print(f"  Matched {len(matched)} games with forecasts")

                # Use forecast data if original is null
                enhanced = enhanced.with_columns([
                    pl.when(pl.col('temp').is_null())
                      .then(pl.col('temperature'))
                      .otherwise(pl.col('temp'))
                      .alias('temp'),
                    pl.when(pl.col('wind').is_null())
                      .then(pl.col('wind_speed'))
                      .otherwise(pl.col('wind'))
                      .alias('wind'),
                    pl.when(pl.col('roof').is_null())
                      .then(pl.col('roof_forecast'))
                      .otherwise(pl.col('roof'))
                      .alias('roof'),
                ])

                # Debug: Check HOU game after transformation
                hou_check = enhanced.filter((pl.col('week') == 12) & (pl.col('home_team') == 'HOU'))
                if len(hou_check) > 0:
                    print(f"  HOU game after transformation: temp={hou_check['temp'][0]}, wind={hou_check['wind'][0]}")

                # Drop forecast columns
                enhanced = enhanced.drop(['temperature', 'wind_speed', 'roof_forecast'])

                print(f"  ✓ Merged forecasts")
            except Exception as e:
                print(f"  Warning: Could not merge {forecast_file.name}: {e}")
    else:
        print("  No forecast files found (future weeks will have null weather)")

    # Load injuries (if available)
    print("Loading injury data...")
    try:
        injuries = nfl.load_injuries(seasons)
        print(f"Loaded {len(injuries)} injury records")

        # Calculate injury scores
        print("Calculating team injury scores...")
        injury_scores = calculate_team_injury_scores(injuries)
        print(f"Calculated injury scores for {len(injury_scores)} team-weeks")
    except (ConnectionError, Exception) as e:
        print(f"Warning: Could not load injury data: {e}")
        print("Continuing without injury data (injury scores will be 0)")
        injury_scores = None

    # Join injury scores if available
    if injury_scores is not None:
        # Join home team injury scores
        enhanced = enhanced.join(
            injury_scores,
            left_on=['season', 'home_team', 'week'],
            right_on=['season', 'team', 'week'],
            how='left'
        ).rename({'injury_score': 'home_injury_score'})

        # Join away team injury scores
        enhanced = enhanced.join(
            injury_scores,
            left_on=['season', 'away_team', 'week'],
            right_on=['season', 'team', 'week'],
            how='left'
        ).rename({'injury_score': 'away_injury_score'})

        # Fill missing injury scores with 0 (no injuries reported)
        enhanced = enhanced.with_columns([
            pl.col('home_injury_score').fill_null(0.0),
            pl.col('away_injury_score').fill_null(0.0),
        ])
    else:
        # No injury data available - set to 0
        enhanced = enhanced.with_columns([
            pl.lit(0.0).alias('home_injury_score'),
            pl.lit(0.0).alias('away_injury_score'),
        ])

    # Calculate injury differential
    enhanced = enhanced.with_columns(
        (pl.col('away_injury_score') - pl.col('home_injury_score')).alias('injury_diff')
    )

    # Cast temp and wind back to Int32 to match original schema
    enhanced = enhanced.with_columns([
        pl.col('temp').cast(pl.Int32, strict=False),
        pl.col('wind').cast(pl.Int32, strict=False),
    ])

    # Summary statistics
    print("\n" + "="*80)
    print("ENHANCED FEATURES SUMMARY")
    print("="*80)
    print(f"\nTotal games: {len(enhanced)}")
    print(f"Seasons: {sorted(enhanced['season'].unique().to_list())}")

    print("\n--- REST DAYS ---")
    print(f"Games with rest data: {enhanced['home_rest'].is_not_null().sum()}")
    print(f"Mean rest (home): {enhanced['home_rest'].mean():.1f} days")
    print(f"Mean rest (away): {enhanced['away_rest'].mean():.1f} days")

    print("\n--- WEATHER ---")
    outdoor_games = enhanced.filter(pl.col('roof').is_in(['outdoors', 'open']))
    print(f"Outdoor games: {len(outdoor_games)} ({len(outdoor_games)/len(enhanced)*100:.1f}%)")
    print(f"Games with temp data: {outdoor_games['temp'].is_not_null().sum()}")
    print(f"Games with wind data: {outdoor_games['wind'].is_not_null().sum()}")
    if outdoor_games['temp'].is_not_null().sum() > 0:
        print(f"Temp range: {outdoor_games['temp'].min()}°F to {outdoor_games['temp'].max()}°F")
        print(f"Wind range: {outdoor_games['wind'].min()} to {outdoor_games['wind'].max()} mph")

    print("\n--- INJURIES ---")
    print(f"Games with injury data: {(enhanced['home_injury_score'] > 0).sum() + (enhanced['away_injury_score'] > 0).sum()}")
    print(f"Mean injury score (home): {enhanced['home_injury_score'].mean():.1f}")
    print(f"Mean injury score (away): {enhanced['away_injury_score'].mean():.1f}")
    print(f"Max injury score: {max(enhanced['home_injury_score'].max(), enhanced['away_injury_score'].max()):.1f}")

    # Debug: Show Week 12 data before export
    week12_debug = enhanced.filter(pl.col('week') == 12)
    print(f"\nWeek 12 data check (showing first 3 games):")
    print(week12_debug.select(['home_team', 'away_team', 'temp', 'wind']).head(3))

    # Export to CSV
    print(f"\nExporting to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    enhanced.write_csv(output_path)

    print(f"✅ Successfully wrote {len(enhanced)} games to {output_path}")
    print("="*80 + "\n")


def main() -> None:
    """Run enhanced features collection from command line."""
    parser = argparse.ArgumentParser(
        description="Collect enhanced features for NFL game predictions"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--seasons',
        type=int,
        nargs='+',
        help='Specific seasons to collect (e.g., 2020 2021 2022)'
    )
    group.add_argument(
        '--start',
        type=int,
        help='Start season (use with --end)'
    )
    parser.add_argument(
        '--end',
        type=int,
        help='End season (use with --start)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('data/nfl/nfl_enhanced_features.csv'),
        help='Output CSV path (default: data/nfl/nfl_enhanced_features.csv)'
    )

    args = parser.parse_args()

    # Determine seasons list
    if args.seasons:
        seasons = args.seasons
    elif args.start and args.end:
        seasons = list(range(args.start, args.end + 1))
    elif args.start:
        parser.error("--start requires --end")
    else:
        parser.error("Must specify either --seasons or --start/--end")

    # Collect features
    collect_enhanced_features(seasons, args.output)


if __name__ == "__main__":
    main()
