{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Calibration curve data for plotting predicted vs observed probabilities.
Essential for evaluating model calibration quality.
*/

with predictions as (
    select
        week_number,
        home_team_win_probability / 10000.0 as predicted_prob,
        case when winning_team = home_team then 1.0 else 0.0 end as actual_outcome
    from {{ ref('nfl_reg_season_predictions') }}
    where include_actuals = true
),

-- Bin predictions into 10% buckets
probability_bins as (
    select
        floor(predicted_prob * 10) / 10.0 as bin_lower,
        floor(predicted_prob * 10) / 10.0 + 0.1 as bin_upper,
        (floor(predicted_prob * 10) / 10.0 + 0.05) as bin_midpoint,
        avg(predicted_prob) as mean_predicted,
        avg(actual_outcome) as mean_observed,
        count(*) as n_predictions,
        stddev(actual_outcome) as stddev_observed,

        -- Calculate standard error for confidence intervals
        stddev(actual_outcome) / sqrt(count(*)) as se_observed
    from predictions
    group by floor(predicted_prob * 10) / 10.0
    having count(*) >= 3  -- Only show bins with sufficient data
)

select
    bin_lower,
    bin_upper,
    bin_midpoint,
    mean_predicted,
    mean_observed,
    n_predictions,
    stddev_observed,
    se_observed,

    -- 95% confidence interval bounds
    mean_observed - (1.96 * se_observed) as ci_lower,
    mean_observed + (1.96 * se_observed) as ci_upper,

    -- Perfect calibration reference line
    bin_midpoint as perfect_calibration,

    -- Calibration error for this bin
    abs(mean_predicted - mean_observed) as calibration_error,

    {{ add_ingestion_timestamp() }}

from probability_bins
order by bin_midpoint
