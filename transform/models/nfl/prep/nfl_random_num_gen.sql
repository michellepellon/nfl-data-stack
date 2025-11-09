{{ config(materialized="table") }}

with
    cte_scenario_gen as (
        select i.generate_series as scenario_id
        from generate_series(1, {{ var("scenarios") }}) as i
    ),
    cte_seeded_random as (
        -- Use deterministic seeded random number generation for reproducibility
        -- Seed is reset for each scenario_id to ensure reproducibility
        select
            i.scenario_id,
            s.game_id,
            -- Combine scenario_id + game_id + global seed for deterministic randomness
            ((hash(i.scenario_id::varchar || '-' || s.game_id::varchar || '-' || {{ var("random_seed") }}::varchar) % 10000) + 1)::smallint as rand_result,
            {{ var("sim_start_game_id") }} as sim_start_game_id,
            current_timestamp as ingested_at
        from cte_scenario_gen as i
        cross join {{ ref("nfl_schedules") }} as s
    )
select * from cte_seeded_random
