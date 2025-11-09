{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Rolling-Origin Backtest Performance

Evaluates model performance across CV splits to estimate out-of-sample performance.
Each test week is scored using only data available up to that point.

Metrics calculated per split:
- Brier score
- Log loss
- Accuracy
- Calibration

This provides a more realistic estimate of model performance than
simple train/test split or using all data at once.
*/

with splits as (
    select * from {{ ref('nfl_backtest_splits') }}
),

predictions as (
    select
        p.week_number,
        p.home_team,
        p.visiting_team,
        p.home_team_win_probability / 10000.0 as predicted_prob,
        case when p.winning_team = p.home_team then 1.0 else 0.0 end as actual_outcome
    from {{ ref('nfl_reg_season_predictions') }} p
    where p.include_actuals = true
),

-- Join predictions with CV splits
split_predictions as (
    select
        s.split_id,
        s.test_week,
        s.split_role,
        p.week_number,
        p.home_team,
        p.visiting_team,
        p.predicted_prob,
        p.actual_outcome
    from splits s
    inner join predictions p
        on s.home_team = p.home_team
        and s.visiting_team = p.visiting_team
        and s.game_week = p.week_number
    where s.split_role = 'test'  -- Only evaluate on test data
),

-- Calculate metrics per split
split_metrics as (
    select
        split_id,
        test_week,

        -- Number of test games
        count(*) as n_test_games,

        -- Brier score
        avg(power(predicted_prob - actual_outcome, 2)) as brier_score,

        -- Log loss
        -avg(
            actual_outcome * ln(greatest(predicted_prob, 0.001)) +
            (1 - actual_outcome) * ln(greatest(1 - predicted_prob, 0.001))
        ) as log_loss,

        -- Accuracy
        avg(case
            when (predicted_prob > 0.5 and actual_outcome = 1) or
                 (predicted_prob <= 0.5 and actual_outcome = 0)
            then 1.0 else 0.0
        end) as accuracy,

        -- Average predicted probability
        avg(predicted_prob) as avg_predicted,

        -- Actual win rate
        avg(actual_outcome) as actual_win_rate,

        -- Calibration error (how far off predictions are from reality)
        abs(avg(predicted_prob) - avg(actual_outcome)) as calibration_error

    from split_predictions
    group by split_id, test_week
)

select
    split_id,
    test_week,
    n_test_games,
    brier_score,
    log_loss,
    accuracy,
    avg_predicted,
    actual_win_rate,
    calibration_error,

    -- Performance rating
    case
        when brier_score < 0.20 then 'Excellent'
        when brier_score < 0.23 then 'Good'
        when brier_score < 0.25 then 'Fair'
        else 'Needs improvement'
    end as performance_rating,

    -- Overall statistics (for aggregation)
    avg(brier_score) over () as overall_brier,
    avg(log_loss) over () as overall_log_loss,
    avg(accuracy) over () as overall_accuracy,

    {{ add_ingestion_timestamp() }}

from split_metrics
order by test_week
