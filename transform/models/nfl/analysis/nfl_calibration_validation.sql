{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Calibration Validation Metrics

Tracks calibration stability over time by analyzing:
- Per-week calibration error (predicted vs actual by probability bin)
- Rolling calibration metrics
- Flags for calibration drift

This complements the walk-forward validation in fit_calibration_temporal.py
by providing ongoing monitoring of calibration quality.
*/

with predictions as (
    select
        week_number,
        home_team,
        visiting_team,
        home_team_win_probability / 10000.0 as predicted_prob,
        case when winning_team = home_team then 1.0 else 0.0 end as actual_outcome
    from {{ ref('nfl_reg_season_predictions') }}
    where include_actuals = true
),

-- Bin predictions into deciles for calibration analysis
binned_predictions as (
    select
        week_number,
        predicted_prob,
        actual_outcome,
        floor(predicted_prob * 10) / 10.0 as prob_bin_lower,
        floor(predicted_prob * 10) / 10.0 + 0.1 as prob_bin_upper
    from predictions
),

-- Calculate per-week, per-bin calibration metrics
weekly_bin_metrics as (
    select
        week_number,
        prob_bin_lower,
        prob_bin_upper,
        count(*) as n_games,
        avg(predicted_prob) as avg_predicted,
        avg(actual_outcome) as avg_actual,
        abs(avg(predicted_prob) - avg(actual_outcome)) as calibration_error
    from binned_predictions
    group by week_number, prob_bin_lower, prob_bin_upper
),

-- Aggregate to per-week calibration metrics
weekly_calibration as (
    select
        week_number,
        sum(n_games) as total_games,

        -- Weighted average calibration error (weighted by bin size)
        sum(calibration_error * n_games) / sum(n_games) as weighted_calibration_error,

        -- Maximum calibration error across bins (worst bin)
        max(calibration_error) as max_calibration_error,

        -- Number of bins with significant miscalibration (>10% error)
        sum(case when calibration_error > 0.10 then 1 else 0 end) as miscalibrated_bins

    from weekly_bin_metrics
    group by week_number
),

-- Add rolling metrics
with_rolling as (
    select
        week_number,
        total_games,
        weighted_calibration_error,
        max_calibration_error,
        miscalibrated_bins,

        -- Rolling 4-week average calibration error
        avg(weighted_calibration_error) over (
            order by week_number
            rows between 3 preceding and current row
        ) as rolling_calibration_error_4w,

        -- Trend: is calibration getting worse?
        weighted_calibration_error - lag(weighted_calibration_error) over (
            order by week_number
        ) as calibration_error_delta,

        -- Cumulative games for context
        sum(total_games) over (
            order by week_number
            rows between unbounded preceding and current row
        ) as cumulative_games

    from weekly_calibration
)

select
    week_number,
    total_games,
    cumulative_games,
    weighted_calibration_error,
    max_calibration_error,
    miscalibrated_bins,
    rolling_calibration_error_4w,
    calibration_error_delta,

    -- Calibration quality rating
    case
        when weighted_calibration_error < 0.03 then 'Excellent'
        when weighted_calibration_error < 0.05 then 'Good'
        when weighted_calibration_error < 0.08 then 'Fair'
        else 'Needs Attention'
    end as calibration_rating,

    -- Drift flag: significant increase in calibration error
    case
        when calibration_error_delta > 0.03 then true
        else false
    end as calibration_drift_flag,

    {{ add_ingestion_timestamp() }}

from with_rolling
order by week_number
