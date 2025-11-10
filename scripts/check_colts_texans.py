#!/usr/bin/env python3
"""Quick script to check Colts/Texans playoff data from DuckDB."""

import duckdb

# Connect to the database
con = duckdb.connect('data/data_catalog/nflds.duckdb')

# Query playoff probabilities
query = """
SELECT
    team,
    division,
    elo,
    playoff_prob,
    bye_prob,
    avg_wins,
    wins_2_5th,
    wins_97_5th,
    vegas_win_total
FROM nfl_playoff_probabilities_ci
WHERE team IN ('IND', 'HOU')
ORDER BY team
"""

try:
    # First try to see what columns exist
    columns = con.execute("DESCRIBE nfl_playoff_probabilities_ci").fetchdf()
    print("\nAvailable columns:")
    print(columns)

    result = con.execute(query).fetchdf()
    print("\nColts/Texans Playoff Data:")
    print("=" * 80)
    print(result.to_string(index=False))
    print("\n")

    # Show the discrepancy
    for _, row in result.iterrows():
        print(f"\n{row['team']}:")
        print(f"  Playoff Probability: {row['playoff_prob']:.1%}")
        print(f"  Projected Wins: {row['avg_wins']:.2f} (95% CI: {row['wins_2_5th']:.2f} - {row['wins_97_5th']:.2f})")
        if 'vegas_win_total' in row:
            print(f"  Vegas Win Total: {row['vegas_win_total']:.1f}")
        print(f"  ELO Rating: {row['elo']:.0f}")

except Exception as e:
    print(f"Error: {e}")
    print("\nAttempting to list available tables...")
    tables = con.execute("SHOW TABLES").fetchdf()
    print(tables)

    # Try a simpler query
    print("\nTrying simpler query...")
    simple_query = "SELECT * FROM nfl_playoff_probabilities_ci WHERE team IN ('IND', 'HOU')"
    result = con.execute(simple_query).fetchdf()
    print(result)

finally:
    con.close()
