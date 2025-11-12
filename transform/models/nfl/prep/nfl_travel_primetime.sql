{{ config(materialized='table') }}

/*
Load travel distance and prime time adjustments from CSV.

This model provides contextual ELO adjustments based on:
- Travel distance: Away teams traveling long distances get negative adjustment
- Altitude: Visiting teams at high altitude (Denver) get negative adjustment
- Prime time: Thursday night games penalize road teams due to short rest

Combined adjustment is applied to away team's effective ELO rating.
*/

select
    game_id,
    season,
    week,
    home_team,
    away_team,
    weekday,
    gametime,
    game_time_slot,

    -- Travel metrics
    travel_distance_miles,
    game_altitude,

    -- Individual adjustments (in ELO points)
    travel_adjustment,          -- -4 ELO per 1,000 miles traveled
    altitude_adjustment,        -- -10 ELO for visiting teams at altitude >4,000 ft
    primetime_adjustment,       -- -5 ELO for road teams on Thursday night

    -- Combined contextual adjustment
    -- Negative values hurt the away team (applied to away team's effective ELO)
    total_contextual_adjustment

from {{ source('nfl', 'travel_primetime') }}
