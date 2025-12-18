{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Closing Line Value (CLV) Analysis

CLV is the gold standard metric for evaluating betting model quality.
It measures how much better your predictions were compared to the
closing line (the most efficient market price).

CLV = Model Probability - Closing Line Probability

Interpretation:
- Positive CLV: Your model predicted higher probability than the market closed at
- Consistent positive CLV over time indicates true edge
- Professional bettors target 2-4% CLV on average

This analysis tracks CLV per game and aggregates by week/season.
*/

with predictions as (
    select
        week_number,
        home_team,
        visiting_team,
        home_win_prob_adjusted as model_prob,
        home_win_prob_ensemble as ensemble_prob,
        vegas_home_win_prob as current_vegas_prob,
        include_actuals
    from {{ ref('nfl_predictions_with_features') }}
    where game_type = 'reg_season'
),

opening_closing as (
    select * from {{ ref('nfl_vegas_opening_closing') }}
),

results as (
    select
        week_number,
        home_team,
        visiting_team,
        case
            when home_team_score > visiting_team_score then 1.0
            when home_team_score < visiting_team_score then 0.0
            else 0.5
        end as home_win_actual
    from {{ ref('nfl_latest_results') }}
    where home_team_score is not null
),

-- Join predictions with opening/closing lines and results
clv_per_game as (
    select
        p.week_number,
        p.home_team,
        p.visiting_team,

        -- Model predictions
        p.model_prob,
        p.ensemble_prob,

        -- Vegas lines
        oc.opening_prob,
        oc.closing_prob,
        oc.spread_movement,

        -- CLV calculations (model vs closing)
        p.model_prob - oc.closing_prob as model_clv,
        p.ensemble_prob - oc.closing_prob as ensemble_clv,

        -- CLV vs opening (alternative metric)
        p.model_prob - oc.opening_prob as model_clv_vs_opening,

        -- Actual outcome for validation
        r.home_win_actual,

        -- Did model agree with direction?
        case
            when (p.model_prob > 0.5 and r.home_win_actual = 1) or
                 (p.model_prob <= 0.5 and r.home_win_actual = 0)
            then 1.0 else 0.0
        end as model_correct,

        -- Did CLV predict winner? (positive CLV + home win or negative CLV + away win)
        case
            when (p.model_prob - oc.closing_prob > 0 and r.home_win_actual = 1) or
                 (p.model_prob - oc.closing_prob < 0 and r.home_win_actual = 0)
            then 1.0 else 0.0
        end as clv_direction_correct,

        -- Has closing line data
        case when oc.closing_prob is not null then true else false end as has_clv_data

    from predictions p
    left join opening_closing oc
        on p.week_number = oc.week_number
        and p.home_team = oc.home_team
        and p.visiting_team = oc.visiting_team
    left join results r
        on p.week_number = r.week_number
        and p.home_team = r.home_team
        and p.visiting_team = r.visiting_team
    where p.include_actuals = true
),

-- Aggregate CLV by week
weekly_clv as (
    select
        week_number,
        count(*) as n_games,
        sum(case when has_clv_data then 1 else 0 end) as n_games_with_clv,

        -- Average CLV
        avg(model_clv) filter (where has_clv_data) as avg_model_clv,
        avg(ensemble_clv) filter (where has_clv_data) as avg_ensemble_clv,

        -- CLV percentiles
        percentile_cont(0.25) within group (order by model_clv) filter (where has_clv_data) as model_clv_p25,
        percentile_cont(0.50) within group (order by model_clv) filter (where has_clv_data) as model_clv_p50,
        percentile_cont(0.75) within group (order by model_clv) filter (where has_clv_data) as model_clv_p75,

        -- Win rates
        avg(model_correct) as model_accuracy,
        avg(clv_direction_correct) filter (where has_clv_data) as clv_accuracy

    from clv_per_game
    group by week_number
)

-- Output both game-level and weekly aggregates
select
    g.week_number,
    g.home_team,
    g.visiting_team,

    -- Model predictions
    g.model_prob,
    g.ensemble_prob,

    -- Vegas lines
    g.opening_prob,
    g.closing_prob,
    g.spread_movement,

    -- CLV metrics
    g.model_clv,
    g.ensemble_clv,
    g.model_clv_vs_opening,

    -- CLV interpretation
    case
        when g.model_clv >= 0.05 then 'Strong positive'
        when g.model_clv >= 0.02 then 'Positive'
        when g.model_clv >= -0.02 then 'Neutral'
        when g.model_clv >= -0.05 then 'Negative'
        else 'Strong negative'
    end as clv_rating,

    -- Outcome
    g.home_win_actual,
    g.model_correct,
    g.clv_direction_correct,
    g.has_clv_data,

    -- Weekly context
    w.avg_model_clv as weekly_avg_clv,
    w.model_clv_p50 as weekly_median_clv,
    w.n_games_with_clv as weekly_clv_games,

    {{ add_ingestion_timestamp() }}

from clv_per_game g
left join weekly_clv w on g.week_number = w.week_number
order by g.week_number, g.home_team
