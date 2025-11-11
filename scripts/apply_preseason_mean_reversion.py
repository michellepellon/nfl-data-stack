"""
Apply Preseason Mean Reversion to ELO Ratings

This script implements FiveThirtyEight's preseason ELO adjustment methodology:
1. Takes end-of-season ELO ratings from previous year
2. Regresses ratings 1/3 toward mean (1505)
3. Optionally blends with Vegas win totals (if available)

Formula (mean reversion only):
    new_elo = old_elo - (1/3) * (old_elo - 1505)

Formula (with Vegas integration):
    regressed_elo = old_elo - (1/3) * (old_elo - 1505)
    vegas_elo = 1505 + (vegas_wins - 8.5) * 25
    preseason_elo = (1/3) * regressed_elo + (2/3) * vegas_elo

Based on: https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/

Usage:
    # Mean reversion only (no Vegas integration)
    python scripts/apply_preseason_mean_reversion.py

    # With Vegas win totals (optional)
    python scripts/apply_preseason_mean_reversion.py --integrate-vegas

    # Custom mean reversion factor (default 1/3)
    python scripts/apply_preseason_mean_reversion.py --reversion-factor 0.4
"""

import pandas as pd
import argparse
from pathlib import Path
from datetime import datetime


def apply_mean_reversion(
    elo_rating: float,
    mean: float = 1505,
    reversion_factor: float = 1/3
) -> float:
    """
    Apply mean reversion to an ELO rating.

    Args:
        elo_rating: Current ELO rating
        mean: Target mean to regress toward (default 1505)
        reversion_factor: Fraction to regress (default 1/3)

    Returns:
        Regressed ELO rating

    Example:
        >>> apply_mean_reversion(1700, 1505, 1/3)
        1635.0  # Moved 1/3 of the way from 1700 toward 1505
    """
    return elo_rating - reversion_factor * (elo_rating - mean)


def vegas_wins_to_elo(win_total: float, mean: float = 1505) -> float:
    """
    Convert Vegas win total to ELO rating.

    Formula: elo = mean + (wins - 8.5) * 25

    This assumes:
    - 8.5 wins = average team (1505 ELO)
    - Each win above/below 8.5 = 25 ELO points

    Args:
        win_total: Vegas over/under win total
        mean: ELO mean (default 1505)

    Returns:
        ELO rating equivalent

    Example:
        >>> vegas_wins_to_elo(12.0)
        1592.5  # 12 wins = 3.5 above average = +87.5 points
    """
    return mean + (win_total - 8.5) * 25


def main():
    parser = argparse.ArgumentParser(
        description="Apply preseason mean reversion to ELO ratings"
    )
    parser.add_argument(
        "--integrate-vegas",
        action="store_true",
        help="Blend with Vegas win totals (2/3 weight)"
    )
    parser.add_argument(
        "--reversion-factor",
        type=float,
        default=1/3,
        help="Fraction to regress toward mean (default: 0.333)"
    )
    parser.add_argument(
        "--mean",
        type=float,
        default=1505,
        help="Target mean for regression (default: 1505)"
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default="data/data_catalog/nfl_latest_elo.parquet",
        help="Input file with end-of-season ELO ratings"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="data/nfl/nfl_team_ratings_generated.csv",
        help="Output file for updated ratings"
    )
    parser.add_argument(
        "--vegas-file",
        type=str,
        default="data/nfl/nfl_team_ratings.csv",
        help="File with Vegas win totals (if using --integrate-vegas)"
    )

    args = parser.parse_args()

    print("🔄 Applying Preseason Mean Reversion")
    print(f"   Reversion factor: {args.reversion_factor:.3f}")
    print(f"   Target mean: {args.mean}")
    print(f"   Vegas integration: {'Yes' if args.integrate_vegas else 'No'}")
    print()

    # Load end-of-season ELO ratings
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"❌ Input file not found: {args.input_file}")
        print("   Run dbt to generate latest ELO ratings first:")
        print("   cd transform && ../uv run dbt run --select nfl_latest_elo")
        return 1

    print(f"📥 Loading end-of-season ratings from: {args.input_file}")
    elo_df = pd.read_parquet(input_path)

    # Verify required columns
    if 'team' not in elo_df.columns or 'elo_rating' not in elo_df.columns:
        print(f"❌ Input file missing required columns: team, elo_rating")
        print(f"   Found columns: {list(elo_df.columns)}")
        return 1

    print(f"   Loaded {len(elo_df)} teams")
    print()

    # Apply mean reversion
    print(f"🔢 Applying mean reversion (factor={args.reversion_factor:.3f}, mean={args.mean})")
    elo_df['elo_rating_previous'] = elo_df['elo_rating']
    elo_df['elo_rating_regressed'] = elo_df['elo_rating'].apply(
        lambda x: apply_mean_reversion(x, args.mean, args.reversion_factor)
    )

    # Show sample of changes
    print("\nSample reversion results:")
    sample = elo_df.nsmallest(3, 'elo_rating_previous')[['team', 'elo_rating_previous', 'elo_rating_regressed']].copy()
    sample = pd.concat([
        sample,
        elo_df.nlargest(3, 'elo_rating_previous')[['team', 'elo_rating_previous', 'elo_rating_regressed']]
    ])
    sample['change'] = sample['elo_rating_regressed'] - sample['elo_rating_previous']
    print(sample.to_string(index=False))
    print()

    # Optional: Integrate Vegas win totals
    if args.integrate_vegas:
        print(f"📊 Integrating Vegas win totals (2/3 weight)")
        vegas_path = Path(args.vegas_file)
        if not vegas_path.exists():
            print(f"❌ Vegas file not found: {args.vegas_file}")
            return 1

        vegas_df = pd.read_csv(vegas_path)
        if 'Team' not in vegas_df.columns or 'Win Total' not in vegas_df.columns:
            print(f"❌ Vegas file missing required columns: Team, Win Total")
            return 1

        # Convert Vegas win totals to ELO
        vegas_df['vegas_elo'] = vegas_df['Win Total'].apply(
            lambda x: vegas_wins_to_elo(x, args.mean)
        )

        # Merge with regressed ELO
        elo_df = elo_df.merge(
            vegas_df[['Team', 'Win Total', 'vegas_elo']],
            left_on='team',
            right_on='Team',
            how='left'
        )

        # Blend: 1/3 regressed + 2/3 vegas
        elo_df['elo_rating_final'] = (
            (1/3) * elo_df['elo_rating_regressed'] +
            (2/3) * elo_df['vegas_elo']
        )

        print(f"   Blended {len(elo_df[elo_df['vegas_elo'].notna()])} teams with Vegas totals")
        print("\nSample blending results:")
        blend_sample = elo_df[elo_df['vegas_elo'].notna()].nsmallest(3, 'Win Total')[
            ['team', 'elo_rating_regressed', 'vegas_elo', 'elo_rating_final', 'Win Total']
        ].copy()
        blend_sample = pd.concat([
            blend_sample,
            elo_df[elo_df['vegas_elo'].notna()].nlargest(3, 'Win Total')[
                ['team', 'elo_rating_regressed', 'vegas_elo', 'elo_rating_final', 'Win Total']
            ]
        ])
        print(blend_sample.to_string(index=False))
        print()

        # Use blended rating as final
        elo_df['elo_rating'] = elo_df['elo_rating_final'].fillna(elo_df['elo_rating_regressed'])
    else:
        # Use regressed rating as final
        elo_df['elo_rating'] = elo_df['elo_rating_regressed']

    # Prepare output
    output_df = elo_df[['team', 'elo_rating']].copy()
    output_df['elo_rating'] = output_df['elo_rating'].round(0).astype(int)
    output_df['generated_at'] = datetime.now().isoformat()

    # Save
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_path, index=False)

    print(f"✅ Saved updated ratings to: {args.output_file}")
    print(f"   {len(output_df)} teams")
    print()

    # Summary statistics
    if args.integrate_vegas:
        print("📈 Summary:")
        print(f"   Previous ELO:  {elo_df['elo_rating_previous'].mean():.1f} ± {elo_df['elo_rating_previous'].std():.1f}")
        print(f"   Regressed ELO: {elo_df['elo_rating_regressed'].mean():.1f} ± {elo_df['elo_rating_regressed'].std():.1f}")
        print(f"   Final ELO:     {elo_df['elo_rating'].mean():.1f} ± {elo_df['elo_rating'].std():.1f}")
    else:
        print("📈 Summary:")
        print(f"   Previous ELO:  {elo_df['elo_rating_previous'].mean():.1f} ± {elo_df['elo_rating_previous'].std():.1f}")
        print(f"   Regressed ELO: {elo_df['elo_rating'].mean():.1f} ± {elo_df['elo_rating'].std():.1f}")
        print(f"   Change:        {(elo_df['elo_rating'] - elo_df['elo_rating_previous']).mean():.1f} points")
    print()
    print("💡 Next steps:")
    print("   1. Review the generated file")
    print("   2. Replace data/nfl/nfl_team_ratings.csv if satisfied")
    print("   3. Run dbt to rebuild models with new ratings")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
