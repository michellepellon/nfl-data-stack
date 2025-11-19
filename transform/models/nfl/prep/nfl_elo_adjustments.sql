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

Adjustment Ranges (RECALIBRATED v2 - more aggressive):
- Rest: ±40 ELO points (10 points per day of rest advantage) - DOUBLED from ±20
- Temperature: -20 to +15 (asymmetric - home advantage in extreme cold if outdoor team)
- Wind: -25 to +10 (asymmetric - home advantage in high wind if outdoor stadium)
- Injuries: ±60 ELO points (1.5x injury score differential)

Total possible range: -145 to +125 ELO points

Rationale for asymmetric weather:
- Week 11 analysis showed symmetric penalties went wrong direction 57% of time
- Outdoor home teams are acclimated to their weather conditions
- Dome teams traveling to cold/windy outdoor games face disadvantage
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

        -- Rest adjustment (±40 cap) - DOUBLED
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
