#!/usr/bin/env python3
"""
Collect Historical NFL Data from nflfastR

This script collects historical NFL game results from nflfastR (2020-2024)
to improve ELO calibration with larger sample sizes.

Usage:
    python scripts/collect_historical_data.py [--start YEAR] [--end YEAR]

Requirements:
    uv add nfl_data_py

Output:
    data/nfl/nfl_results_historical.csv
"""

import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime
import time
from io import StringIO

def collect_nfl_data(start_year=2020, end_year=2024, output_dir='data/nfl'):
    """
    Collect NFL historical data from nflfastR

    Parameters:
    - start_year: First season to collect (default 2020)
    - end_year: Last season to collect (default 2024)
    - output_dir: Output directory for CSV files

    Returns:
    - DataFrame with collected games
    """

    print(f"\n{'='*80}")
    print(f"Collecting NFL Historical Data from nflfastR")
    print(f"{'='*80}\n")
    print(f"Seasons: {start_year}-{end_year}")
    print(f"Output: {output_dir}/\n")

    # Collect schedule data (includes scores)
    print("📥 Downloading schedule data from nflfastR...")
    seasons = list(range(start_year, end_year + 1))

    try:
        # Download data from Pro Football Reference
        # They provide simple HTML tables that pandas can parse
        all_seasons = []

        for season in seasons:
            url = f"https://www.pro-football-reference.com/years/{season}/games.htm"
            print(f"  Downloading season {season} from Pro Football Reference...")

            # Read HTML tables from the page
            tables = pd.read_html(url)

            # The games table is usually the first table
            df = tables[0]

            # Add season column
            df['Season'] = season

            all_seasons.append(df)

            # Be respectful - add small delay between requests
            if season < end_year:
                time.sleep(1)

        schedule = pd.concat(all_seasons, ignore_index=True)
    except Exception as e:
        print(f"\n❌ Error downloading data: {e}")
        print("Check your internet connection and try again.\n")
        return None

    print(f"✓ Downloaded {len(schedule)} total games")

    # Pro Football Reference has the same schema as our current data!
    # Just need to filter and clean
    print("\n🔄 Transforming data to match schema...")

    # Remove header rows that sometimes appear in the middle of the table
    schedule = schedule[schedule['Week'] != 'Week'].copy()

    # Filter to completed games only (exclude future games)
    schedule['PtsW'] = pd.to_numeric(schedule['PtsW'], errors='coerce')
    schedule['PtsL'] = pd.to_numeric(schedule['PtsL'], errors='coerce')
    completed = schedule[
        (schedule['PtsW'].notna()) &
        (schedule['PtsL'].notna())
    ].copy()

    print(f"✓ Filtered to {len(completed)} completed games")

    # Rename columns to match our schema
    # Pro Football Reference has 'Unnamed: 5' for the @ symbol and 'Date.1' for boxscore link
    completed = completed.rename(columns={
        'Unnamed: 5': '@',
        'Date.1': 'boxscore'
    })

    # Fill missing @ symbols with empty string
    completed['@'] = completed['@'].fillna('')

    # Create output DataFrame matching our schema
    output = completed[['Week', 'Day', 'Date', 'Time', 'Winner/tie', '@', 'Loser/tie', 'boxscore',
                        'PtsW', 'PtsL', 'YdsW', 'TOW', 'YdsL', 'TOL', 'Season']].copy()

    # Convert numeric columns
    output['Week'] = pd.to_numeric(output['Week'], errors='coerce')
    output['PtsW'] = output['PtsW'].astype(int)
    output['PtsL'] = output['PtsL'].astype(int)

    # Sort by season, week, and date
    output = output.sort_values(['Season', 'Week', 'Date']).reset_index(drop=True)

    # Summary statistics
    print("\n📊 Data Summary:")
    print(f"   Total games: {len(output)}")
    print(f"   Seasons: {output['Season'].min()} - {output['Season'].max()}")
    print(f"   Date range: {output['Date'].min()} to {output['Date'].max()}")

    # Detect playoff games (Week > 18 for regular season)
    output['is_playoff'] = output['Week'] > 18

    print(f"   Regular season: {len(output[~output['is_playoff']])} games")
    print(f"   Playoffs: {len(output[output['is_playoff']])} games")

    # Games per season
    print("\n   Games per season:")
    for season in sorted(output['Season'].unique()):
        season_games = len(output[output['Season'] == season])
        print(f"      {season}: {season_games} games")

    # Remove the is_playoff column before saving
    output = output.drop(columns=['is_playoff'])

    # Save to CSV
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    output_file = output_path / 'nfl_results_historical.csv'
    output.to_csv(output_file, index=False)

    print(f"\n💾 Saved to: {output_file}")
    print(f"   File size: {output_file.stat().st_size / 1024:.1f} KB")

    # Validation checks
    print("\n✓ Validation Checks:")
    checks = [
        ("No missing scores", output[['PtsW', 'PtsL']].notna().all().all()),
        ("No missing teams", output[['Winner/tie', 'Loser/tie']].notna().all().all()),
        ("All games have winners", (output['Winner/tie'] != '').all()),
        ("All games have weeks", output['Week'].notna().all()),
        ("Scores are integers", output['PtsW'].dtype == 'int64'),
    ]

    for check_name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}")

    if not all(check[1] for check in checks):
        print("\n⚠️  Warning: Some validation checks failed!")
    else:
        print("\n✅ All validation checks passed!")

    # Next steps
    print(f"\n{'='*80}")
    print("Next Steps:")
    print("{'='*80}")
    print("1. Update dbt source configuration:")
    print("   Add to transform/models/nfl/raw/sources.yml:")
    print("""
   sources:
     - name: nfl
       tables:
         - name: nfl_results_historical
           description: 'Historical NFL results from nflfastR (2020-2024)'
""")
    print("\n2. Modify nfl_latest_results to use historical data")
    print("   (or create separate historical processing)")
    print("\n3. Re-run the full build:")
    print("   just build")
    print("\n4. Check improved calibration:")
    print("   just calibration")
    print(f"\n{'='*80}\n")

    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Collect historical NFL data from nflfastR'
    )
    parser.add_argument(
        '--start',
        type=int,
        default=2020,
        help='Start year (default: 2020)'
    )
    parser.add_argument(
        '--end',
        type=int,
        default=2024,
        help='End year (default: 2024)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/nfl',
        help='Output directory (default: data/nfl)'
    )

    args = parser.parse_args()

    # Collect data
    df = collect_nfl_data(
        start_year=args.start,
        end_year=args.end,
        output_dir=args.output
    )

    if df is not None:
        print("✅ Data collection completed successfully!\n")
    else:
        print("❌ Data collection failed.\n")
        exit(1)
