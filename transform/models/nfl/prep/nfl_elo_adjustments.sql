{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Calculate ELO adjustments from contextual features (rest, weather, injuries).

Adjustments are applied to the home team's ELO advantage:
- Positive adjustment = favors home team
- Negative adjustment = favors away team

Adjustment Ranges (RECALIBRATED v3 - QB-specific injury weighting):
- Rest: ±40 ELO points (10 points per day of rest advantage)
- Temperature: -20 to +15 (asymmetric - home advantage in extreme cold if outdoor team)
- Wind: -25 to +10 (asymmetric - home advantage in high wind if outdoor stadium)
- QB Injuries: ±50 ELO points (1.25x qb_injury_score - backup QB is ~40 ELO downgrade)
- Non-QB Injuries: ±30 ELO points (0.5x non_qb_injury_diff)

Total possible range: -165 to +135 ELO points

Rationale for QB-specific weighting:
- Research shows QB injuries impact win probability more than any other position
- A backup QB represents a ~30-50 ELO point downgrade
- Non-QB injuries are aggregated across multiple players, so per-point impact is lower
*/

with features as (
    select * from {{ ref('nfl_raw_enhanced_features') }}
),

adjustments as (
    select
        game_id,
        season,
        week,
        home_team,
        away_team,

        -- Rest adjustment (±40 cap)
        -- 10 ELO points per day of rest advantage
        greatest(-40, least(40, rest_diff * 10.0)) as rest_adjustment,

        -- Temperature adjustment (asymmetric - home advantage in extreme cold)
        -- Outdoor home teams acclimated to weather, dome teams struggle in cold
        case
            when roof in ('dome', 'closed') then 0
            when temp is null then 0
            when temp < 32 then
                -- Extreme cold: +15 for outdoor home, -20 for dome home
                case when roof = 'outdoors' then 15 else -20 end
            when temp < 50 then
                -- Moderate cold: +5 for outdoor home, -10 for dome home
                case when roof = 'outdoors' then 5 else -10 end
            when temp > 75 then -5   -- Heat (symmetric penalty)
            else 0                   -- Ideal conditions
        end as temp_adjustment,

        -- Wind adjustment (asymmetric - home advantage in high wind)
        -- Outdoor home teams used to wind, dome teams not
        case
            when roof in ('dome', 'closed') then 0
            when wind is null then 0
            when wind >= 20 then
                -- Severe wind: +10 for outdoor home, -25 for dome home
                case when roof = 'outdoors' then 10 else -25 end
            when wind >= 10 then
                -- Moderate wind: +5 for outdoor home, -10 for dome home
                case when roof = 'outdoors' then 5 else -10 end
            else 0                    -- Calm
        end as wind_adjustment,

        -- QB Injury adjustment (±50 cap) - HIGH IMPACT
        -- 1.25 ELO points per QB injury point (max 40 * 1.25 = 50)
        -- Rationale: Backup QB represents 30-50 ELO downgrade
        greatest(-50, least(50, qb_injury_diff * 1.25)) as qb_injury_adjustment,

        -- Non-QB Injury adjustment (±30 cap) - MODERATE IMPACT
        -- 0.5 ELO points per non-QB injury point
        -- Lower multiplier because non-QB injuries are spread across multiple players
        greatest(-30, least(30, non_qb_injury_diff * 0.5)) as non_qb_injury_adjustment,

        -- Combined injury adjustment (for backwards compatibility)
        greatest(-80, least(80,
            qb_injury_diff * 1.25 + non_qb_injury_diff * 0.5
        )) as injury_adjustment,

        -- Metadata for analysis
        rest_diff,
        roof,
        temp,
        wind,
        home_injury_score,
        away_injury_score,
        injury_diff,
        home_qb_injury_score,
        away_qb_injury_score,
        qb_injury_diff,
        home_non_qb_injury_score,
        away_non_qb_injury_score,
        non_qb_injury_diff

    from features
)

select
    game_id,
    season,
    week,
    home_team,
    away_team,

    -- Individual adjustments
    rest_adjustment,
    temp_adjustment,
    wind_adjustment,
    temp_adjustment + wind_adjustment as weather_adjustment,
    qb_injury_adjustment,
    non_qb_injury_adjustment,
    injury_adjustment,

    -- Total adjustment (sum of all features)
    rest_adjustment + temp_adjustment + wind_adjustment + injury_adjustment as total_adjustment,

    -- Feature metadata
    rest_diff,
    roof,
    temp,
    wind,
    home_injury_score,
    away_injury_score,
    injury_diff,
    home_qb_injury_score,
    away_qb_injury_score,
    qb_injury_diff,
    home_non_qb_injury_score,
    away_non_qb_injury_score,
    non_qb_injury_diff,

    {{ add_ingestion_timestamp() }}

from adjustments
