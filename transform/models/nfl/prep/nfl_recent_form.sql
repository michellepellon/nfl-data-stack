{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Recent Form / Momentum Calculation

Calculates team momentum based on performance in recent games (last 3 games).
Key metrics:
- Win streak/loss streak
- Performance vs expectation (actual margin vs predicted margin)
- Scoring trend (points scored/allowed trending up or down)

Adjustments applied to ELO predictions:
- Win streak (3 games): +25 ELO
- Loss streak (3 games): -25 ELO
- Performance vs expectation: ±15 ELO based on avg point differential

Total possible momentum adjustment: ±40 ELO points
*/

with game_results as (
    select
        game_id,
        week_number,
        home_team,
        visiting_team,
        home_team_score,
        visiting_team_score,
        home_team_score - visiting_team_score as home_margin,
        case
            when home_team_score > visiting_team_score then home_team
            when visiting_team_score > home_team_score then visiting_team
            else null
        end as winner
    from {{ ref('nfl_latest_results') }}
    where home_team_score is not null
        and visiting_team_score is not null
),

-- Get all games for each team
team_games as (
    -- Home games
    select
        game_id,
        week_number,
        home_team as team,
        visiting_team as opponent,
        home_team_score as team_score,
        visiting_team_score as opponent_score,
        home_margin as margin,
        case when winner = home_team then 1 else 0 end as won
    from game_results

    union all

    -- Away games
    select
        game_id,
        week_number,
        visiting_team as team,
        home_team as opponent,
        visiting_team_score as team_score,
        home_team_score as opponent_score,
        -home_margin as margin,
        case when winner = visiting_team then 1 else 0 end as won
    from game_results
),

-- For each team/week, get games from PREVIOUS weeks only
team_games_with_weeks as (
    select
        *,
        row_number() over (
            partition by team
            order by game_id
        ) as game_seq
    from team_games
),

-- Get all teams and all weeks (for calculating momentum even for future weeks)
all_teams as (
    select distinct team from team_games
),

all_weeks as (
    select distinct week_number from {{ ref('nfl_schedules') }}
    where type = 'reg_season'
),

team_week_combinations as (
    select t.team, w.week_number
    from all_teams t
    cross join all_weeks w
    where w.week_number > 1  -- Week 1 has no prior games
),

-- Calculate last 3 games for each team at each week
-- Only include games that happened BEFORE the target week
recent_games as (
    select
        target.week_number,
        target.team,
        history.game_id,
        history.won,
        history.margin,
        history.team_score,
        history.opponent_score,
        row_number() over (
            partition by target.team, target.week_number
            order by history.game_id desc
        ) as games_ago
    from team_week_combinations target
    inner join team_games_with_weeks history
        on history.team = target.team
        and history.week_number < target.week_number  -- Only games from PREVIOUS weeks
),

-- Aggregate last 3 games stats
recent_form_stats as (
    select
        week_number,
        team,
        count(*) as games_played,
        sum(won) as wins_last_3,
        sum(case when won = 0 then 1 else 0 end) as losses_last_3,
        avg(margin) as avg_margin_last_3,
        avg(team_score) as avg_points_scored_last_3,
        avg(opponent_score) as avg_points_allowed_last_3
    from recent_games
    where games_ago <= 3
    group by week_number, team
),

-- Calculate momentum adjustments
momentum_adjustments as (
    select
        week_number,
        team,
        games_played,
        wins_last_3,
        losses_last_3,
        avg_margin_last_3,
        avg_points_scored_last_3,
        avg_points_allowed_last_3,

        -- Win streak adjustment
        case
            when games_played = 3 and wins_last_3 = 3 then 25.0  -- 3-game win streak
            when games_played >= 2 and wins_last_3 = 2 then 15.0 -- 2-game win streak
            when games_played = 3 and losses_last_3 = 3 then -25.0  -- 3-game losing streak
            when games_played >= 2 and losses_last_3 = 2 then -15.0 -- 2-game losing streak
            else 0.0
        end as streak_adjustment,

        -- Performance vs expectation adjustment
        -- Positive margin = winning by large margins
        -- Scale: ±15 ELO for ±10 point average margin
        greatest(-15.0, least(15.0, avg_margin_last_3 * 1.5)) as performance_adjustment,

        -- Total momentum adjustment
        greatest(-40.0, least(40.0,
            case
                when games_played = 3 and wins_last_3 = 3 then 25.0
                when games_played >= 2 and wins_last_3 = 2 then 15.0
                when games_played = 3 and losses_last_3 = 3 then -25.0
                when games_played >= 2 and losses_last_3 = 2 then -15.0
                else 0.0
            end +
            greatest(-15.0, least(15.0, avg_margin_last_3 * 1.5))
        )) as total_momentum_adjustment

    from recent_form_stats
    where games_played >= 2  -- Need at least 2 games of history
)

select
    week_number,
    team,
    games_played,
    wins_last_3,
    losses_last_3,
    avg_margin_last_3,
    avg_points_scored_last_3,
    avg_points_allowed_last_3,
    streak_adjustment,
    performance_adjustment,
    total_momentum_adjustment,

    {{ add_ingestion_timestamp() }}

from momentum_adjustments
order by week_number desc, total_momentum_adjustment desc
