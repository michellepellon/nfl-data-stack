{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Vegas Opening and Closing Lines

Pivots Vegas line history to provide opening and closing lines side-by-side
for each game. This enables Closing Line Value (CLV) calculations.

Line Movement = Closing - Opening
- Positive movement: Line moved toward home team
- Negative movement: Line moved toward away team

Sharp money typically moves lines, so beating the closing line is a
strong indicator of a positive expected value bet.
*/

with history as (
    select * from {{ ref('nfl_raw_vegas_history') }}
),

schedule as (
    select
        week_number,
        home_team,
        visiting_team
    from {{ ref('nfl_schedules') }}
    where type = 'reg_season'
),

-- Get the earliest opening snapshot per game
opening_lines as (
    select
        home_team,
        away_team,
        home_spread as opening_spread,
        home_moneyline as opening_moneyline,
        home_win_prob_consensus as opening_prob,
        snapshot_time as opening_snapshot_time,
        row_number() over (
            partition by home_team, away_team
            order by snapshot_time asc
        ) as rn
    from history
    where snapshot_type = 'opening'
),

-- Get the latest closing snapshot per game
closing_lines as (
    select
        home_team,
        away_team,
        home_spread as closing_spread,
        home_moneyline as closing_moneyline,
        home_win_prob_consensus as closing_prob,
        snapshot_time as closing_snapshot_time,
        row_number() over (
            partition by home_team, away_team
            order by snapshot_time desc
        ) as rn
    from history
    where snapshot_type = 'closing'
),

-- Join opening and closing lines
combined as (
    select
        s.week_number,
        s.home_team,
        s.visiting_team,

        -- Opening lines
        o.opening_spread,
        o.opening_moneyline,
        o.opening_prob,
        o.opening_snapshot_time,

        -- Closing lines
        c.closing_spread,
        c.closing_moneyline,
        c.closing_prob,
        c.closing_snapshot_time,

        -- Line movement
        c.closing_spread - o.opening_spread as spread_movement,
        c.closing_prob - o.opening_prob as prob_movement,

        -- Has both opening and closing
        case
            when o.opening_spread is not null and c.closing_spread is not null
            then true else false
        end as has_both_lines

    from schedule s
    left join opening_lines o
        on s.home_team = o.home_team
        and s.visiting_team = o.away_team
        and o.rn = 1
    left join closing_lines c
        on s.home_team = c.home_team
        and s.visiting_team = c.away_team
        and c.rn = 1
)

select
    week_number,
    home_team,
    visiting_team,

    -- Opening lines
    opening_spread,
    opening_moneyline,
    opening_prob,
    opening_snapshot_time,

    -- Closing lines
    closing_spread,
    closing_moneyline,
    closing_prob,
    closing_snapshot_time,

    -- Line movement analysis
    spread_movement,
    prob_movement,
    has_both_lines,

    -- Movement direction interpretation
    case
        when spread_movement > 0.5 then 'Moved toward home'
        when spread_movement < -0.5 then 'Moved toward away'
        else 'Stable'
    end as movement_direction,

    -- Significant movement flag (>1 point spread change)
    case when abs(spread_movement) > 1.0 then true else false end as significant_movement,

    {{ add_ingestion_timestamp() }}

from combined
order by week_number, home_team
