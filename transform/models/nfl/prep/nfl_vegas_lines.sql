{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Vegas Lines Integration

Processes Vegas odds from The Odds API and matches them to our schedule.
Provides consensus win probabilities for ensemble predictions.

Data source: scripts/collect_vegas_lines.py
*/

with raw_vegas as (
    select * from read_parquet('../data/nfl/vegas_lines_2025.parquet')
),

schedule as (
    select
        week_number,
        home_team,
        visiting_team
    from {{ ref('nfl_schedules') }}
    where type = 'reg_season'
),

-- Match Vegas lines to schedule by teams
vegas_with_week as (
    select
        s.week_number,
        v.home_team,
        v.away_team as visiting_team,
        v.home_spread,
        v.away_spread,
        v.home_moneyline,
        v.away_moneyline,
        v.home_win_prob_moneyline,
        v.away_win_prob_moneyline,
        v.home_win_prob_spread,
        v.away_win_prob_spread,
        v.home_win_prob_consensus,
        v.away_win_prob_consensus,
        v.bookmaker,
        v.commence_time,
        v.fetched_at
    from raw_vegas v
    inner join schedule s
        on s.home_team = v.home_team
        and s.visiting_team = v.away_team
)

select
    week_number,
    home_team,
    visiting_team,

    -- Spreads
    home_spread,
    away_spread,

    -- Moneylines (American odds)
    home_moneyline,
    away_moneyline,

    -- Win probabilities from different sources
    home_win_prob_moneyline,
    away_win_prob_moneyline,
    home_win_prob_spread,
    away_win_prob_spread,

    -- Consensus probability (average of moneyline and spread)
    home_win_prob_consensus,
    away_win_prob_consensus,

    -- Metadata
    bookmaker,
    commence_time,
    fetched_at,

    {{ add_ingestion_timestamp() }}

from vegas_with_week
order by week_number, home_team
