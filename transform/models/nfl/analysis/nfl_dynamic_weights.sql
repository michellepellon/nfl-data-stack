{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Dynamic Ensemble Weights Calculation

Calculates weights for ELO and Vegas models based on rolling performance.

Design decisions:
- Rolling window: 4 weeks (~60 games) for stability
- Weighting method: Inverse Brier score (lower error = higher weight)
- Weight bounds: 0.25 to 0.75 (moderate, maintains diversification)
- Cold start: Weeks 1-4 use default 0.5/0.5

Formula:
  raw_weight = 1 / (brier_score + epsilon)
  normalized_weight = raw_weight / sum(raw_weights)
  bounded_weight = greatest(0.25, least(0.75, normalized_weight))
*/

with per_model_perf as (
    select * from {{ ref('nfl_per_model_performance') }}
    where model_name in ('elo', 'vegas')
),

-- Get rolling Brier scores for each model at each week
-- Use the NEXT week for predictions (we predict week N using performance from weeks 1 to N-1)
model_performance_for_weighting as (
    select
        model_name,
        week_number + 1 as prediction_week,  -- These weights apply to NEXT week's predictions
        rolling_brier_4w,
        weeks_in_window
    from per_model_perf
),

-- Pivot to get ELO and Vegas performance side by side
pivoted_performance as (
    select
        prediction_week,
        max(case when model_name = 'elo' then rolling_brier_4w end) as elo_brier,
        max(case when model_name = 'vegas' then rolling_brier_4w end) as vegas_brier,
        max(case when model_name = 'elo' then weeks_in_window end) as elo_weeks,
        max(case when model_name = 'vegas' then weeks_in_window end) as vegas_weeks
    from model_performance_for_weighting
    group by prediction_week
),

-- Calculate raw weights using inverse Brier score
-- Lower Brier = better = higher weight
raw_weights as (
    select
        prediction_week,
        elo_brier,
        vegas_brier,
        elo_weeks,
        vegas_weeks,

        -- Inverse Brier weights (add small epsilon to avoid division by zero)
        1.0 / (elo_brier + 0.001) as elo_raw_weight,
        case
            when vegas_brier is not null then 1.0 / (vegas_brier + 0.001)
            else null
        end as vegas_raw_weight

    from pivoted_performance
),

-- Normalize weights to sum to 1.0, then apply bounds
normalized_weights as (
    select
        prediction_week,
        elo_brier,
        vegas_brier,
        elo_weeks,
        coalesce(vegas_weeks, 0) as vegas_weeks,

        -- Normalized weights (before bounds)
        case
            when vegas_raw_weight is not null then
                elo_raw_weight / (elo_raw_weight + vegas_raw_weight)
            else 1.0  -- No Vegas data, 100% ELO
        end as elo_weight_unbounded,

        case
            when vegas_raw_weight is not null then
                vegas_raw_weight / (elo_raw_weight + vegas_raw_weight)
            else 0.0  -- No Vegas data, 0% Vegas
        end as vegas_weight_unbounded

    from raw_weights
),

-- Apply bounds and cold start logic
bounded_weights as (
    select
        prediction_week as week_number,
        elo_brier,
        vegas_brier,
        elo_weeks,
        vegas_weeks,
        elo_weight_unbounded,
        vegas_weight_unbounded,

        -- Apply bounds: 0.25 to 0.75
        -- But only if we have enough data (at least 4 weeks for both models)
        case
            -- Cold start: not enough ELO history
            when elo_weeks < 4 then 0.50
            -- No Vegas data at all
            when vegas_weeks = 0 then 1.0
            -- Cold start: not enough Vegas history
            when vegas_weeks < 4 then 0.50
            -- Normal: apply bounds
            else greatest(0.25, least(0.75, elo_weight_unbounded))
        end as elo_weight,

        case
            -- Cold start: not enough ELO history
            when elo_weeks < 4 then 0.50
            -- No Vegas data at all
            when vegas_weeks = 0 then 0.0
            -- Cold start: not enough Vegas history
            when vegas_weeks < 4 then 0.50
            -- Normal: apply bounds
            else greatest(0.25, least(0.75, vegas_weight_unbounded))
        end as vegas_weight,

        -- Flag cold start weeks
        case
            when elo_weeks < 4 or vegas_weeks < 4 then true
            else false
        end as is_cold_start

    from normalized_weights
)

select
    week_number,
    elo_weight,
    vegas_weight,

    -- Verify weights sum to 1.0 (or close to it with rounding)
    elo_weight + vegas_weight as weight_sum,

    -- Metadata for debugging/analysis
    elo_brier as elo_rolling_brier,
    vegas_brier as vegas_rolling_brier,
    elo_weeks as elo_weeks_in_window,
    vegas_weeks as vegas_weeks_in_window,
    is_cold_start,

    -- Weight change from 50/50 baseline
    elo_weight - 0.5 as elo_weight_delta,
    vegas_weight - 0.5 as vegas_weight_delta,

    {{ add_ingestion_timestamp() }}

from bounded_weights
order by week_number
