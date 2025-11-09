{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Model performance metrics demonstrating statistical rigor.
Includes calibration analysis, Brier score decomposition, and resolution metrics.
*/

with calibration as (
    select * from {{ ref('nfl_elo_calibration') }}
),

-- Base predictions (for Brier, log loss, accuracy, calibration)
predictions as (
    select
        week_number,
        home_team,
        visiting_team,
        home_team_win_probability / 10000.0 as predicted_prob,
        elo_diff,
        case when winning_team = home_team then 1.0 else 0.0 end as actual_outcome
    from {{ ref('nfl_reg_season_predictions') }}
    where include_actuals = true
),

-- Predictions with scores (for ATS metrics)
predictions_with_scores as (
    select
        p.week_number,
        p.home_team,
        p.visiting_team,
        p.home_team_win_probability / 10000.0 as predicted_prob,
        p.elo_diff,
        -- Predicted spread from ELO (positive = home team favored)
        -- ELO diff of 100 points ≈ 2.8 point spread
        p.elo_diff / 35.7 as predicted_spread,
        -- Actual margin (positive = home team won by that much)
        r.home_team_score - r.visiting_team_score as actual_margin
    from {{ ref('nfl_reg_season_predictions') }} p
    inner join {{ ref('nfl_latest_results') }} r
        on p.week_number = r.week_number
        and p.home_team = r.home_team
        and p.visiting_team = r.visiting_team
    where p.include_actuals = true
      and r.home_team_score is not null
),

-- Calculate Brier score by week
weekly_brier as (
    select
        week_number,
        avg(power(predicted_prob - actual_outcome, 2)) as brier_score,
        count(*) as n_games
    from predictions
    group by week_number
),

-- Calculate log loss by week
weekly_logloss as (
    select
        week_number,
        -avg(
            actual_outcome * ln(greatest(predicted_prob, 0.001)) +
            (1 - actual_outcome) * ln(greatest(1 - predicted_prob, 0.001))
        ) as log_loss
    from predictions
    group by week_number
),

-- Calculate accuracy by week
weekly_accuracy as (
    select
        week_number,
        avg(case
            when (predicted_prob > 0.5 and actual_outcome = 1) or
                 (predicted_prob <= 0.5 and actual_outcome = 0)
            then 1.0 else 0.0
        end) as accuracy
    from predictions
    group by week_number
),

-- Calculate ATS (Against The Spread) error by week
weekly_ats as (
    select
        week_number,
        -- Mean Absolute Error of spread prediction
        avg(abs(predicted_spread - actual_margin)) as mae_spread,

        -- Root Mean Square Error of spread prediction
        sqrt(avg(power(predicted_spread - actual_margin, 2))) as rmse_spread,

        -- ATS accuracy (did we beat the spread?)
        avg(case
            when (predicted_spread > 0 and actual_margin > 0) or
                 (predicted_spread < 0 and actual_margin < 0) or
                 (predicted_spread = 0 and actual_margin = 0)
            then 1.0 else 0.0
        end) as ats_accuracy,

        -- Average spread error (bias check - should be ~0)
        avg(predicted_spread - actual_margin) as mean_spread_error,

        count(*) as n_games_with_scores
    from predictions_with_scores
    group by week_number
),

-- Probability bins for calibration
probability_bins as (
    select
        floor(predicted_prob * 10) / 10.0 as prob_bin_lower,
        floor(predicted_prob * 10) / 10.0 + 0.1 as prob_bin_upper,
        avg(predicted_prob) as avg_predicted,
        avg(actual_outcome) as avg_actual,
        count(*) as n_predictions,
        stddev(actual_outcome) as actual_stddev
    from predictions
    group by floor(predicted_prob * 10) / 10.0
),

-- Brier score decomposition
brier_decomp as (
    select
        -- Reliability: How well calibrated are the probabilities?
        avg(power(avg_predicted - avg_actual, 2) * n_predictions) /
            sum(n_predictions) as reliability,

        -- Resolution: How much do predictions vary from base rate?
        avg(power(avg_actual - (select avg(actual_outcome) from predictions), 2) * n_predictions) /
            sum(n_predictions) as resolution,

        -- Uncertainty: Inherent unpredictability (base rate variance)
        (select avg(actual_outcome) from predictions) *
        (1 - (select avg(actual_outcome) from predictions)) as uncertainty

    from probability_bins
)

-- Combine all metrics
select
    wb.week_number,
    wb.brier_score,
    wb.n_games,

    wl.log_loss,
    wa.accuracy,

    -- ATS metrics
    ats.mae_spread,
    ats.rmse_spread,
    ats.ats_accuracy,
    ats.mean_spread_error,
    ats.n_games_with_scores,

    -- Overall metrics (constant per row for dashboard aggregation)
    (select avg(brier_score) from weekly_brier) as overall_brier,
    (select avg(log_loss) from weekly_logloss) as overall_logloss,
    (select avg(accuracy) from weekly_accuracy) as overall_accuracy,
    (select avg(mae_spread) from weekly_ats) as overall_mae_spread,
    (select avg(rmse_spread) from weekly_ats) as overall_rmse_spread,
    (select avg(ats_accuracy) from weekly_ats) as overall_ats_accuracy,

    -- Calibration metrics
    (select reliability from brier_decomp) as brier_reliability,
    (select resolution from brier_decomp) as brier_resolution,
    (select uncertainty from brier_decomp) as brier_uncertainty,

    -- Derived insights
    case
        when wb.brier_score < 0.20 then 'Excellent'
        when wb.brier_score < 0.23 then 'Good'
        when wb.brier_score < 0.25 then 'Fair'
        else 'Needs improvement'
    end as performance_rating,

    {{ add_ingestion_timestamp() }}

from weekly_brier wb
left join weekly_logloss wl on wb.week_number = wl.week_number
left join weekly_accuracy wa on wb.week_number = wa.week_number
left join weekly_ats ats on wb.week_number = ats.week_number
