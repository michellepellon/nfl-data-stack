{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Per-Model Performance Tracking

Tracks performance metrics for each prediction model separately:
- ELO model (with features + momentum adjustments)
- Vegas model (consensus implied probability)
- Ensemble model (50/50 weighted combination - fixed for consistency)

This enables dynamic ensemble weighting based on recent model performance.

NOTE: Uses base predictions (not nfl_predictions_with_features) to avoid
circular dependencies with dynamic weights.
*/

with base_predictions as (
    select * from {{ ref('nfl_reg_season_predictions') }}
    where include_actuals = true
      and type = 'reg_season'
),

adjustments as (
    select * from {{ ref('nfl_elo_adjustments') }}
),

recent_form as (
    select * from {{ ref('nfl_recent_form') }}
),

vegas_lines as (
    select * from {{ ref('nfl_vegas_lines') }}
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

-- Calculate predictions from base models (avoiding circular dependency)
predictions_calculated as (
    select
        p.week_number,
        p.home_team,
        p.visiting_team,
        p.elo_diff,
        coalesce(adj.total_adjustment, 0) as total_adj,
        coalesce(home_form.total_momentum_adjustment, 0) as home_momentum,
        coalesce(away_form.total_momentum_adjustment, 0) as away_momentum,
        vegas.home_win_prob_consensus as vegas_prob,

        -- ELO probability (with features + momentum)
        1.0 / (1.0 + power(10, -((
            p.elo_diff +
            coalesce(adj.total_adjustment, 0) +
            coalesce(home_form.total_momentum_adjustment, 0) -
            coalesce(away_form.total_momentum_adjustment, 0) +
            52
        ) / 400.0))) as elo_prob,

        -- Fixed 50/50 ensemble (for consistent performance tracking)
        case
            when vegas.home_win_prob_consensus is not null then
                0.5 * (1.0 / (1.0 + power(10, -((
                    p.elo_diff +
                    coalesce(adj.total_adjustment, 0) +
                    coalesce(home_form.total_momentum_adjustment, 0) -
                    coalesce(away_form.total_momentum_adjustment, 0) +
                    52
                ) / 400.0)))) +
                0.5 * vegas.home_win_prob_consensus
            else
                1.0 / (1.0 + power(10, -((
                    p.elo_diff +
                    coalesce(adj.total_adjustment, 0) +
                    coalesce(home_form.total_momentum_adjustment, 0) -
                    coalesce(away_form.total_momentum_adjustment, 0) +
                    52
                ) / 400.0)))
        end as ensemble_prob

    from base_predictions p
    left join adjustments adj
        on p.week_number = adj.week
        and p.home_short = adj.home_team
        and p.vis_short = adj.away_team
    left join recent_form home_form
        on p.week_number = home_form.week_number
        and p.home_team = home_form.team
    left join recent_form away_form
        on p.week_number = away_form.week_number
        and p.visiting_team = away_form.team
    left join vegas_lines vegas
        on p.week_number = vegas.week_number
        and p.home_team = vegas.home_team
        and p.visiting_team = vegas.visiting_team
),

-- Join predictions with actual outcomes
predictions_with_outcomes as (
    select
        p.week_number,
        p.home_team,
        p.visiting_team,
        p.elo_prob,
        p.vegas_prob,
        p.ensemble_prob,
        r.home_win_actual
    from predictions_calculated p
    inner join results r
        on p.week_number = r.week_number
        and p.home_team = r.home_team
        and p.visiting_team = r.visiting_team
),

-- Calculate metrics for ELO model
elo_weekly as (
    select
        'elo' as model_name,
        week_number,
        count(*) as n_games,
        avg(power(elo_prob - home_win_actual, 2)) as brier_score,
        -avg(
            home_win_actual * ln(greatest(elo_prob, 0.001)) +
            (1 - home_win_actual) * ln(greatest(1 - elo_prob, 0.001))
        ) as log_loss,
        avg(case
            when (elo_prob > 0.5 and home_win_actual = 1) or
                 (elo_prob <= 0.5 and home_win_actual = 0)
            then 1.0 else 0.0
        end) as accuracy
    from predictions_with_outcomes
    group by week_number
),

-- Calculate metrics for Vegas model (only games with Vegas lines)
vegas_weekly as (
    select
        'vegas' as model_name,
        week_number,
        count(*) as n_games,
        avg(power(vegas_prob - home_win_actual, 2)) as brier_score,
        -avg(
            home_win_actual * ln(greatest(vegas_prob, 0.001)) +
            (1 - home_win_actual) * ln(greatest(1 - vegas_prob, 0.001))
        ) as log_loss,
        avg(case
            when (vegas_prob > 0.5 and home_win_actual = 1) or
                 (vegas_prob <= 0.5 and home_win_actual = 0)
            then 1.0 else 0.0
        end) as accuracy
    from predictions_with_outcomes
    where vegas_prob is not null
    group by week_number
),

-- Calculate metrics for Ensemble model
ensemble_weekly as (
    select
        'ensemble' as model_name,
        week_number,
        count(*) as n_games,
        avg(power(ensemble_prob - home_win_actual, 2)) as brier_score,
        -avg(
            home_win_actual * ln(greatest(ensemble_prob, 0.001)) +
            (1 - home_win_actual) * ln(greatest(1 - ensemble_prob, 0.001))
        ) as log_loss,
        avg(case
            when (ensemble_prob > 0.5 and home_win_actual = 1) or
                 (ensemble_prob <= 0.5 and home_win_actual = 0)
            then 1.0 else 0.0
        end) as accuracy
    from predictions_with_outcomes
    group by week_number
),

-- Combine all models
all_models as (
    select * from elo_weekly
    union all
    select * from vegas_weekly
    union all
    select * from ensemble_weekly
)

select
    model_name,
    week_number,
    n_games,
    brier_score,
    log_loss,
    accuracy,

    -- Rolling 4-week metrics for dynamic weighting
    avg(brier_score) over (
        partition by model_name
        order by week_number
        rows between 3 preceding and current row
    ) as rolling_brier_4w,

    avg(accuracy) over (
        partition by model_name
        order by week_number
        rows between 3 preceding and current row
    ) as rolling_accuracy_4w,

    -- Count weeks in rolling window (for cold start detection)
    count(*) over (
        partition by model_name
        order by week_number
        rows between 3 preceding and current row
    ) as weeks_in_window,

    {{ add_ingestion_timestamp() }}

from all_models
order by week_number, model_name
