#!/usr/bin/env python3
"""
Collect 2025 NFL Season Results

Fetches actual 2025 game results from Pro Football Reference to update
ELO ratings and re-run simulations for live Week 10+ predictions.

Usage:
    python scripts/collect_2025_results.py

Output:
    data/nfl/nfl_results_2025.csv
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

def collect_2025_results():
    """Collect 2025 NFL season results from Pro Football Reference."""

    print(f"\n{'='*80}")
    print(f"Collecting 2025 NFL Season Results")
    print(f"{'='*80}\n")

    url = "https://www.pro-football-reference.com/years/2025/games.htm"
    print(f"📥 Downloading from: {url}")

    try:
        tables = pd.read_html(url)
        df = tables[0]
        print(f"✓ Downloaded {len(df)} total games")
    except Exception as e:
        print(f"\n❌ Error downloading data: {e}")
        return None

    print("\n🔄 Cleaning and transforming data...")

    # Remove header rows that appear mid-table
    df = df[df['Week'] != 'Week'].copy()

    # Convert scores to numeric
    df['PtsW'] = pd.to_numeric(df['PtsW'], errors='coerce')
    df['PtsL'] = pd.to_numeric(df['PtsL'], errors='coerce')

    # Filter to completed games only
    completed = df[
        (df['PtsW'].notna()) &
        (df['PtsL'].notna())
    ].copy()

    print(f"✓ Found {len(completed)} completed games")

    # Rename columns to match our schema
    output = completed.rename(columns={
        'Unnamed: 5': '@',
        'Unnamed: 7': 'boxscore'  # Placeholder
    }).copy()

    # Add Season column
    output['Season'] = 2025

    # Select and order columns to match existing schema
    output = output[[
        'Week', 'Day', 'Date', 'Time',
        'Winner/tie', '@', 'Loser/tie',
        'PtsW', 'PtsL', 'YdsW', 'TOW', 'YdsL', 'TOL',
        'Season'
    ]].copy()

    # Data quality checks
    print(f"\n📊 Data Summary:")
    print(f"   Total completed games: {len(output)}")

    # Group by week
    weeks = output.groupby('Week').size().sort_index()
    print(f"\n   Games by week:")
    for week, count in weeks.items():
        print(f"      Week {week}: {count} games")

    # Save to CSV
    output_dir = Path('data/nfl')
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / 'nfl_results_2025.csv'
    output.to_csv(output_path, index=False)

    file_size = output_path.stat().st_size / 1024
    print(f"\n💾 Saved to: {output_path}")
    print(f"   File size: {file_size:.1f} KB")

    # Validation
    print(f"\n✓ Validation Checks:")
    checks = {
        'No missing scores': output['PtsW'].notna().all() and output['PtsL'].notna().all(),
        'No missing teams': output['Winner/tie'].notna().all() and output['Loser/tie'].notna().all(),
        'All have weeks': output['Week'].notna().all(),
    }

    for check, passed in checks.items():
        status = '✅' if passed else '❌'
        print(f"   {status} {check}")

    print(f"\n{'='*80}")
    print("Next Steps:")
    print(f"{'='*80}\n")
    print("1. Replace old results file:")
    print("   cp data/nfl/nfl_results_2025.csv data/nfl/nfl_results.csv")
    print("\n2. Re-run dbt build to update ELO ratings:")
    print("   just build")
    print("\n3. Update webpage data:")
    print("   python update_webpage.py --week 10")
    print("\n4. View updated predictions:")
    print("   just web")
    print(f"\n{'='*80}\n")

    return output

if __name__ == "__main__":
    result = collect_2025_results()

    if result is not None:
        print("✅ 2025 data collection completed successfully!")
    else:
        print("❌ Data collection failed")
        exit(1)
