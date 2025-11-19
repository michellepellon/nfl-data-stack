#!/usr/bin/env python3
"""
Collect Weather Forecasts for Upcoming NFL Games

Uses the National Weather Service (NWS) API to fetch 7-day forecasts for NFL stadiums.
NWS API is free, no API key required, and very reliable.

API Documentation: https://www.weather.gov/documentation/services-web-api

Usage:
    python scripts/collect_weather_forecasts.py --week 12
"""

import requests
import pandas as pd
import polars as pl
from pathlib import Path
from datetime import datetime, timedelta
import time
import argparse


def get_nws_forecast(latitude: float, longitude: float) -> dict:
    """
    Get weather forecast from National Weather Service API.

    Args:
        latitude: Stadium latitude
        longitude: Stadium longitude

    Returns:
        Dict with temperature and wind speed forecast
    """
    try:
        # Step 1: Get the forecast grid endpoint for this location
        points_url = f"https://api.weather.gov/points/{latitude},{longitude}"
        headers = {'User-Agent': '(NFL Prediction Model, contact@example.com)'}

        response = requests.get(points_url, headers=headers, timeout=10)
        response.raise_for_status()

        points_data = response.json()
        forecast_url = points_data['properties']['forecast']

        # Step 2: Get the actual forecast
        time.sleep(0.5)  # Be nice to the API
        forecast_response = requests.get(forecast_url, headers=headers, timeout=10)
        forecast_response.raise_for_status()

        forecast_data = forecast_response.json()
        periods = forecast_data['properties']['periods']

        if not periods:
            return {'temperature': None, 'wind_speed': None}

        # Get the first period (current/next forecast)
        first_period = periods[0]

        temperature = first_period.get('temperature')
        wind_speed_str = first_period.get('windSpeed', '0 mph')

        # Parse wind speed (format: "10 mph" or "5 to 10 mph")
        try:
            if 'to' in wind_speed_str:
                # Take the higher value for "5 to 10 mph"
                wind_parts = wind_speed_str.split('to')
                wind_speed = int(wind_parts[1].strip().split()[0])
            else:
                wind_speed = int(wind_speed_str.split()[0])
        except (ValueError, IndexError):
            wind_speed = 0

        return {
            'temperature': temperature,
            'wind_speed': wind_speed,
            'forecast_time': first_period.get('startTime'),
            'short_forecast': first_period.get('shortForecast', '')
        }

    except Exception as e:
        print(f"  Warning: Could not fetch forecast for ({latitude}, {longitude}): {e}")
        return {'temperature': None, 'wind_speed': None}


def main():
    parser = argparse.ArgumentParser(description='Collect weather forecasts for NFL games')
    parser.add_argument('--week', type=int, help='NFL week number (optional, defaults to current week)')
    args = parser.parse_args()

    print("=" * 80)
    print("Collecting Weather Forecasts for NFL Games")
    print("=" * 80)

    # Load stadium coordinates
    stadiums_df = pd.read_csv(Path(__file__).parent.parent / 'data' / 'nfl' / 'stadium_coordinates.csv')
    print(f"\n✓ Loaded {len(stadiums_df)} stadium locations")

    # Load schedule to get upcoming games
    schedule_df = pd.read_parquet(Path(__file__).parent.parent / 'data' / 'data_catalog' / 'nfl_schedules.parquet')

    # Filter to specified week or find current week
    if args.week:
        target_week = args.week
    else:
        # Find the next week with games
        results_df = pd.read_parquet(Path(__file__).parent.parent / 'data' / 'data_catalog' / 'nfl_latest_results.parquet')
        completed_weeks = results_df[results_df['home_team_score'].notna()]['week_number'].max()
        target_week = completed_weeks + 1

    week_games = schedule_df[
        (schedule_df['week_number'] == target_week) &
        (schedule_df['type'] == 'reg_season')
    ].copy()

    print(f"\n✓ Found {len(week_games)} games in Week {target_week}")

    # Collect forecasts for each game
    forecasts = []

    for idx, game in week_games.iterrows():
        home_team = game['home_team']

        # Get stadium info
        stadium_info = stadiums_df[stadiums_df['team'] == home_team]

        if stadium_info.empty:
            print(f"\n✗ No stadium data for {home_team}")
            continue

        stadium_info = stadium_info.iloc[0]
        lat = stadium_info['latitude']
        lon = stadium_info['longitude']
        roof = stadium_info['roof_type']

        print(f"\n{game['visiting_team']} @ {home_team}")
        print(f"  Stadium: {stadium_info['stadium_name']} ({roof})")
        print(f"  Location: {lat}, {lon}")

        # Get weather forecast
        if roof in ['dome', 'closed']:
            print(f"  Weather: N/A (dome)")
            weather = {'temperature': None, 'wind_speed': None}
        else:
            print(f"  Fetching forecast...")
            weather = get_nws_forecast(lat, lon)

            if weather['temperature'] is not None:
                print(f"  Forecast: {weather['temperature']}°F, {weather['wind_speed']} mph wind")
                print(f"  Conditions: {weather.get('short_forecast', 'N/A')}")
            else:
                print(f"  Warning: Could not get forecast")

        forecasts.append({
            'week': target_week,
            'game_id': str(game['game_id']),  # Convert to string to match schedule format
            'home_team': home_team,
            'away_team': game['visiting_team'],
            'stadium_name': stadium_info['stadium_name'],
            'latitude': lat,
            'longitude': lon,
            'roof': roof,
            'temperature': weather.get('temperature'),
            'wind_speed': weather.get('wind_speed'),
            'forecast_time': weather.get('forecast_time'),
            'short_forecast': weather.get('short_forecast', ''),
            'collected_at': datetime.now().isoformat()
        })

    # Save to CSV
    output_dir = Path(__file__).parent.parent / 'data' / 'nfl'
    output_file = output_dir / f'weather_forecasts_week{target_week}.csv'

    forecasts_df = pd.DataFrame(forecasts)
    forecasts_df.to_csv(output_file, index=False)

    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"✓ Collected forecasts for {len(forecasts)} games")
    print(f"✓ Saved to {output_file}")

    # Show stats
    outdoor_games = forecasts_df[forecasts_df['roof'] == 'outdoors']
    print(f"\nOutdoor games: {len(outdoor_games)}")
    if len(outdoor_games) > 0:
        print(f"Avg temperature: {outdoor_games['temperature'].mean():.1f}°F")
        print(f"Avg wind speed: {outdoor_games['wind_speed'].mean():.1f} mph")
        print(f"\nColdest: {outdoor_games['temperature'].min():.0f}°F at {outdoor_games.loc[outdoor_games['temperature'].idxmin(), 'stadium_name']}")
        print(f"Windiest: {outdoor_games['wind_speed'].max():.0f} mph at {outdoor_games.loc[outdoor_games['wind_speed'].idxmax(), 'stadium_name']}")


if __name__ == '__main__':
    main()
