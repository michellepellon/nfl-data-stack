{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Rolling-Origin Cross-Validation Splits

Creates time-series CV splits for backtesting the ELO model.
Each split uses all prior weeks as training data and one future week as test.

Key principles:
- No data leakage: Test data is always in the future
- Rolling origin: Training window grows as we move forward in time
- Week-level splits: Each week is a separate test fold

Example for 2025 season:
- Split 1: Train on weeks 1-8, test on week 9
- Split 2: Train on weeks 1-9, test on week 10
- Split 3: Train on weeks 1-10, test on week 11
- etc.
*/

with games_with_results as (
    select
        week_number,
        game_id,
        home_team,
        visiting_team,
        winning_team
    from {{ ref('nfl_latest_results') }}
    where week_number is not null
      and winning_team is not null
),

-- Get all unique weeks with completed games
weeks_with_data as (
    select distinct
        week_number,
        count(*) over (partition by week_number) as games_in_week,
        count(*) over (order by week_number) as cumulative_games
    from games_with_results
),

-- Define CV splits (minimum 4 weeks training, test each subsequent week)
cv_splits as (
    select
        test.week_number as test_week,
        train.week_number as train_week,
        row_number() over (partition by test.week_number order by train.week_number) as train_week_seq,
        count(*) over (partition by test.week_number) as n_train_weeks,

        -- Split metadata
        test.week_number - min(train.week_number) over (partition by test.week_number) as weeks_lookback,

        -- Split identifier
        'week_' || test.week_number as split_id

    from weeks_with_data test
    cross join weeks_with_data train

    -- Only use prior weeks for training
    where train.week_number < test.week_number
      -- Require minimum 4 weeks of training data
      and test.week_number >= 5
),

-- Assign games to splits
split_assignments as (
    select
        s.split_id,
        s.test_week,
        s.train_week,
        s.n_train_weeks,
        s.weeks_lookback,
        g.game_id,
        g.home_team,
        g.visiting_team,
        g.winning_team,
        g.week_number as game_week,

        case
            when g.week_number = s.test_week then 'test'
            when g.week_number = s.train_week then 'train'
            else null
        end as split_role

    from cv_splits s
    left join games_with_results g
        on g.week_number = s.test_week
        or g.week_number = s.train_week

    where split_role is not null
)

select
    split_id,
    test_week,
    game_week,
    split_role,
    game_id,
    home_team,
    visiting_team,
    winning_team,

    -- Split statistics (for validation)
    n_train_weeks,
    weeks_lookback,
    count(*) over (partition by split_id, split_role) as games_in_split,

    {{ add_ingestion_timestamp() }}

from split_assignments
order by split_id, split_role desc, game_week, game_id
