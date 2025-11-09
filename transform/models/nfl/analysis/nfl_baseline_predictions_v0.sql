{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Baseline ELO Predictions Snapshot - Version 0.0
Frozen: 2025-11-08

This model captures the v0.0 baseline predictions for reproducibility.
All future model versions can be compared against this baseline.

Model Configuration:
- K-factor: 20
- Home advantage: 52 ELO points
- Random seed: 42
- MOV multiplier: FiveThirtyEight formula

Performance (2025 season):
- Brier Score: 0.1702
- Log Loss: 0.5155
- Accuracy: 75.1%
*/

with predictions as (
    select
        '0.0' as model_version,
        current_timestamp as snapshot_timestamp,

        -- Game identifiers
        week_number,
        game_id,
        type as game_type,
        home_team,
        home_short,
        visiting_team,
        vis_short,

        -- ELO ratings at time of prediction
        home_team_elo_rating,
        visiting_team_elo_rating,
        elo_diff,

        -- Predictions
        home_team_win_probability / 10000.0 as home_win_prob,
        (10000 - home_team_win_probability) / 10000.0 as away_win_prob,

        -- Predicted winner
        winning_team as predicted_winner,

        -- Actual outcome (if available)
        include_actuals,

        -- Model configuration (for reproducibility)
        20 as k_factor,
        52 as home_advantage,
        42 as random_seed,
        occurances as num_simulations,

        {{ add_ingestion_timestamp() }}

    from {{ ref('nfl_reg_season_predictions') }}
    where include_actuals = true
)

select * from predictions
order by week_number, game_id
