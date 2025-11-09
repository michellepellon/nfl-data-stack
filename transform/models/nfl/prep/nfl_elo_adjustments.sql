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

Adjustment Ranges:
- Rest: ±20 ELO points (5 points per day of rest advantage)
- Temperature: -10 to 0 (outdoor only, symmetric penalty for extreme conditions)
- Wind: -15 to 0 (outdoor only, symmetric penalty for high wind)
- Injuries: ±60 ELO points (1.5x injury score differential)

Total possible range: -105 to +80 ELO points
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

        -- Rest adjustment (±20 cap)
        -- 5 ELO points per day of rest advantage
        greatest(-20, least(20, rest_diff * 5.0)) as rest_adjustment,

        -- Temperature adjustment (outdoor only, symmetric)
        -- Extreme conditions hurt both teams equally
        case
            when roof in ('dome', 'closed') then 0
            when temp is null then 0
            when temp < 32 then -10  -- Extreme cold
            when temp < 50 then -5   -- Moderate cold
            when temp > 75 then -3   -- Heat
            else 0                   -- Ideal conditions
        end as temp_adjustment,

        -- Wind adjustment (outdoor only, symmetric)
        -- High wind reduces passing effectiveness for both teams
        case
            when roof in ('dome', 'closed') then 0
            when wind is null then 0
            when wind >= 20 then -15  -- Severe wind
            when wind >= 10 then -5   -- Moderate wind
            else 0                    -- Calm
        end as wind_adjustment,

        -- Injury adjustment (±60 cap)
        -- Positive = away team more injured (helps home)
        -- 1.5 ELO points per injury score point
        greatest(-60, least(60, injury_diff * 1.5)) as injury_adjustment,

        -- Metadata for analysis
        rest_diff,
        roof,
        temp,
        wind,
        home_injury_score,
        away_injury_score,
        injury_diff

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

    {{ add_ingestion_timestamp() }}

from adjustments
