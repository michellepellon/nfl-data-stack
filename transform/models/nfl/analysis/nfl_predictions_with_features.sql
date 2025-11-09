{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Enhanced prediction view combining ELO predictions with feature adjustments.
Designed for Tufte-style dashboards: information-dense, minimal chartjunk.
*/

with predictions as (
    select * from {{ ref('nfl_reg_season_predictions') }}
),

adjustments as (
    select * from {{ ref('nfl_elo_adjustments') }}
),

ratings as (
    select
        team,
        team_short,
        conf,
        division,
        elo_rating,
        original_rating,
        elo_rating - original_rating as season_delta
    from {{ ref('nfl_ratings') }}
)

select
    -- Game identifiers
    p.game_id,
    p.week_number,
    -- Season (current NFL season)
    2025 as season,
    p.type as game_type,

    -- Home team
    p.home_team,
    p.home_short,
    home_ratings.conf as home_conf,
    home_ratings.division as home_div,
    p.home_team_elo_rating,
    home_ratings.season_delta as home_elo_delta,

    -- Visiting team
    p.visiting_team,
    p.vis_short,
    vis_ratings.conf as vis_conf,
    vis_ratings.division as vis_div,
    p.visiting_team_elo_rating,
    vis_ratings.season_delta as vis_elo_delta,

    -- Base prediction (no features)
    p.elo_diff,
    p.home_team_win_probability / 10000.0 as home_win_prob_base,
    (10000 - p.home_team_win_probability) / 10000.0 as away_win_prob_base,
    p.american_odds as odds_american,

    -- Feature adjustments
    coalesce(adj.rest_adjustment, 0) as rest_adj,
    coalesce(adj.temp_adjustment, 0) as temp_adj,
    coalesce(adj.wind_adjustment, 0) as wind_adj,
    coalesce(adj.weather_adjustment, 0) as weather_adj,
    coalesce(adj.injury_adjustment, 0) as injury_adj,
    coalesce(adj.total_adjustment, 0) as total_adj,

    -- Feature metadata (for explanatory tooltips)
    adj.rest_diff as rest_days_diff,
    adj.roof as roof_type,
    adj.temp as temperature,
    adj.wind as wind_speed,
    adj.home_injury_score,
    adj.away_injury_score,
    adj.injury_diff,

    -- Adjusted ELO difference and probability
    -- (Adjustment is added to home advantage, affecting effective ELO diff)
    p.elo_diff + coalesce(adj.total_adjustment, 0) as elo_diff_adjusted,

    -- Calculate adjusted win probability using logistic function
    -- P(home wins) = 1 / (1 + 10^(-(elo_diff_adjusted + home_adv) / 400))
    -- Using standard 52 home advantage
    1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + 52) / 400.0))) as home_win_prob_adjusted,

    -- Predicted winner
    p.winning_team,
    case
        when (1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + 52) / 400.0)))) > 0.5
        then p.home_team
        else p.visiting_team
    end as predicted_winner_adjusted,

    -- Prediction confidence (distance from 50%)
    abs((p.home_team_win_probability / 10000.0) - 0.5) * 2 as confidence_base,
    abs((1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + 52) / 400.0)))) - 0.5) * 2 as confidence_adjusted,

    -- Simulation metadata
    p.occurances as sim_count,
    p.include_actuals,

    {{ add_ingestion_timestamp() }}

from predictions p
left join adjustments adj
    on p.week_number = adj.week
    and p.home_short = adj.home_team
    and p.vis_short = adj.away_team
left join ratings home_ratings on p.home_team = home_ratings.team
left join ratings vis_ratings on p.visiting_team = vis_ratings.team
