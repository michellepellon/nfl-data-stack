#!/usr/bin/env python3
"""
Collect NFL Scores from ESPN API

Fetches real-time NFL game results from ESPN's unofficial API to update
ELO ratings and re-run simulations for live predictions.

ESPN API updates immediately after games finish, providing faster updates
than Pro Football Reference.

Usage:
    python scripts/collect_espn_scores.py

Output:
    data/nfl/nfl_results_2025.csv (updated with latest scores)
"""

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

def fetch_espn_scoreboard(year=2025, season_type=2):
    """
    Fetch NFL scoreboard data from ESPN API.

    Args:
        year: NFL season year
        season_type: 1=preseason, 2=regular, 3=postseason

    Returns:
        List of game dictionaries
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    params = {
        'limit': 1000,
        'dates': year
    }

    print(f"📥 Fetching from ESPN API...")
    print(f"   URL: {url}")

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(f"✓ API request successful")
        return data
    except Exception as e:
        print(f"❌ Error fetching from ESPN: {e}")
        return None


def parse_espn_games(data):
    """Parse ESPN API response into game records."""
    if not data or 'events' not in data:
        print("❌ No events found in API response")
        return []

    games = []
    events = data['events']

    print(f"📊 Processing {len(events)} events...")

    for event in events:
        try:
            # Get basic event info
            event_id = event.get('id')
            name = event.get('name')
            status = event['status']['type']['name']
            status_state = event['status']['type'].get('state', '')

            # Only process TRULY completed games (STATUS_FINAL and state='post')
            # This filters out scheduled, in-progress, and postponed games
            if status != 'STATUS_FINAL' or status_state != 'post':
                continue

            # Get week number
            week = event.get('week', {}).get('number')
            if not week:
                continue

            # Get date and time
            date_str = event.get('date', '')
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))

            # Get teams and scores
            competitions = event.get('competitions', [])
            if not competitions:
                continue

            comp = competitions[0]
            competitors = comp.get('competitors', [])

            if len(competitors) != 2:
                continue

            # ESPN format: index 0 = home, index 1 = away
            home_team = competitors[0]
            away_team = competitors[1]

            home_score = int(home_team.get('score', 0))
            away_score = int(away_team.get('score', 0))

            home_name = home_team['team']['displayName']
            away_name = away_team['team']['displayName']

            # Skip invalid team names (Pro Bowl, All-Star games, etc.)
            invalid_names = ['NFC', 'AFC', 'North', 'South', 'East', 'West', 'American', 'National']
            if any(invalid in [home_name, away_name] for invalid in invalid_names):
                continue

            # Determine winner/loser
            if home_score > away_score:
                winner = home_name
                loser = away_name
                pts_w = home_score
                pts_l = away_score
            else:
                winner = away_name
                loser = home_name
                pts_w = away_score
                pts_l = home_score

            # Get stats if available
            home_stats = home_team.get('statistics', [])
            away_stats = away_team.get('statistics', [])

            # Find total yards and turnovers
            def get_stat(stats, name):
                for stat in stats:
                    if stat.get('name') == name:
                        return float(stat.get('displayValue', 0))
                return 0

            home_yards = get_stat(home_stats, 'totalYards')
            away_yards = get_stat(away_stats, 'totalYards')
            home_to = get_stat(home_stats, 'turnovers')
            away_to = get_stat(away_stats, 'turnovers')

            # Assign stats to winner/loser
            if home_score > away_score:
                yds_w = home_yards
                yds_l = away_yards
                to_w = home_to
                to_l = away_to
            else:
                yds_w = away_yards
                yds_l = home_yards
                to_w = away_to
                to_l = home_to

            game_record = {
                'Week': week,
                'Day': date_obj.strftime('%a'),
                'Date': date_obj.strftime('%Y-%m-%d'),
                'Time': date_obj.strftime('%I:%M%p').lstrip('0'),
                'Winner/tie': winner,
                '@': '@' if winner == away_name else '',  # @ if away team won
                'Loser/tie': loser,
                'PtsW': pts_w,
                'PtsL': pts_l,
                'YdsW': yds_w if yds_w > 0 else None,
                'TOW': to_w if to_w > 0 else None,
                'YdsL': yds_l if yds_l > 0 else None,
                'TOL': to_l if to_l > 0 else None,
                'Season': 2025
            }

            games.append(game_record)

        except Exception as e:
            print(f"⚠️  Error parsing event {event.get('id')}: {e}")
            continue

    print(f"✓ Parsed {len(games)} completed games")
    return games


def collect_espn_scores():
    """Main collection function."""
    print(f"\n{'='*80}")
    print(f"Collecting 2025 NFL Results from ESPN API")
    print(f"{'='*80}\n")

    # Fetch data
    data = fetch_espn_scoreboard(year=2025, season_type=2)
    if not data:
        return None

    # Parse games
    games = parse_espn_games(data)
    if not games:
        print("❌ No completed games found")
        return None

    # Convert to DataFrame
    df = pd.DataFrame(games)

    # Sort by week and date
    df = df.sort_values(['Week', 'Date'])

    # Data quality summary
    print(f"\n📊 Data Summary:")
    print(f"   Total completed games: {len(df)}")

    weeks = df.groupby('Week').size().sort_index()
    print(f"\n   Games by week:")
    for week, count in weeks.items():
        print(f"      Week {week}: {count} games")

    # Save to CSV
    output_dir = Path('data/nfl')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write to nfl_results.csv (the file dbt reads)
    output_path = output_dir / 'nfl_results.csv'
    df.to_csv(output_path, index=False)

    # Also save a timestamped backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = output_dir / f'nfl_results_2025_{timestamp}.csv'
    df.to_csv(backup_path, index=False)

    file_size = output_path.stat().st_size / 1024
    print(f"\n💾 Saved to: {output_path}")
    print(f"   File size: {file_size:.1f} KB")
    print(f"   Last updated: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")

    print(f"\n{'='*80}\n")

    return df


if __name__ == "__main__":
    result = collect_espn_scores()

    if result is not None:
        print("✅ ESPN data collection completed successfully!")
    else:
        print("❌ Data collection failed")
        exit(1)
