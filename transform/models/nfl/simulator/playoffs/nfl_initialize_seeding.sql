with
    cte_teams as (
        select
            scenario_id,
            conf,
            winning_team,
            seed,
            elo_rating
        from {{ ref("nfl_reg_season_end") }}
        where season_rank <= 7
    )

select
    t.*,
    {{ var("sim_start_game_id") }} as sim_start_game_id,
    {{ add_ingestion_timestamp() }}
from cte_teams t


