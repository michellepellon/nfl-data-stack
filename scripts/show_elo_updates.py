#!/usr/bin/env python3
"""
Display ELO Rating Updates and Analysis
Usage: python scripts/show_elo_updates.py [--top N]
"""
import pandas as pd
import argparse

def show_elo_updates(top_n=10):
    # Load ELO rollforward data from DuckDB
    import duckdb
    conn = duckdb.connect('data/data_catalog/nflds.duckdb', read_only=True)
    df = conn.execute("SELECT * FROM nfl_elo_rollforward ORDER BY game_id").df()
    conn.close()

    print("\n" + "="*120)
    print(f"{'ELO RATING UPDATES - MARGIN-OF-VICTORY ANALYSIS':^120}")
    print("="*120 + "\n")

    # Calculate additional metrics
    df['elo_change_magnitude'] = df['elo_change'].abs()
    df['home_won'] = df['elo_change'] < 0  # negative elo_change means home team gained rating

    # Find biggest upsets (largest ELO changes)
    print(f"\n{'TOP UPSETS (Largest ELO Changes)':^120}")
    print("-"*120)
    print(f"{'Game':<10} {'Matchup':<50} {'Score':<15} {'ELO Change':<15} {'Margin':<10}")
    print("-"*120)

    upsets = df.nlargest(top_n, 'elo_change_magnitude')
    for _, row in upsets.iterrows():
        visiting_team = row['visiting_team']
        home_team = row['home_team']
        winner = row['winning_team']

        # Format score
        if row['home_won']:
            score = f"{int(row['margin'])} (H)"
        else:
            score = f"{int(row['margin'])} (A)"

        matchup = f"{visiting_team} @ {home_team}"
        if winner:
            matchup += f" ({winner} won)"

        print(f"{int(row['game_id']):<10} {matchup:<50} {score:<15} {row['elo_change']:+.1f}{'':<10} {int(row['margin']):<10}")

    # Show current ELO ratings
    print(f"\n{'CURRENT ELO RATINGS (After All Completed Games)':^120}")
    print("-"*120)

    # Get latest ELO for each team
    home_latest = df.groupby('home_team').agg({
        'home_team_elo_rating': 'last',
        'elo_change': lambda x: -sum(x)  # home team: negative elo_change means gains
    }).reset_index()
    home_latest.columns = ['team', 'final_elo', 'total_change']

    visiting_latest = df.groupby('visiting_team').agg({
        'visiting_team_elo_rating': 'last',
        'elo_change': 'sum'  # visiting team: positive elo_change means gains
    }).reset_index()
    visiting_latest.columns = ['team', 'final_elo', 'total_change']

    # Combine and calculate final ratings
    all_teams = pd.concat([home_latest, visiting_latest])
    team_elo = all_teams.groupby('team').agg({
        'final_elo': 'first',  # Get initial rating
        'total_change': 'sum'  # Sum all changes
    }).reset_index()
    team_elo['current_elo'] = team_elo['final_elo'] + team_elo['total_change']
    team_elo = team_elo.sort_values('current_elo', ascending=False)

    print(f"{'Team':<30} {'Initial ELO':<15} {'Total Change':<15} {'Current ELO':<15}")
    print("-"*120)
    for _, row in team_elo.iterrows():
        print(f"{row['team']:<30} {row['final_elo']:>15.1f} {row['total_change']:>+15.1f} {row['current_elo']:>15.1f}")

    # Summary statistics
    print(f"\n{'SUMMARY STATISTICS':^120}")
    print("="*120)
    print(f"Total games processed: {len(df)}")
    print(f"Average ELO change magnitude: {df['elo_change_magnitude'].mean():.1f}")
    print(f"Max ELO change: {df['elo_change_magnitude'].max():.1f}")
    print(f"Min ELO change: {df['elo_change_magnitude'].min():.1f}")
    print(f"Average margin of victory: {df['margin'].mean():.1f}")
    print(f"Largest blowout: {df['margin'].max():.0f} points")
    print("="*120 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Display ELO rating updates and analysis')
    parser.add_argument('--top', type=int, default=10, help='Number of top upsets to show')
    args = parser.parse_args()

    show_elo_updates(args.top)
