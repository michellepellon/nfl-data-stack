select
    seed.team,
    seed.team_short,
    ratings."Win Total" as win_total,
    ratings."ELO rating" as elo_rating,
    seed.conf,
    seed.division,
    {{ add_ingestion_timestamp() }}
from {{ ref("nfl_teams_seed") }} seed
left join {{ source("nfl", "nfl_team_ratings") }} ratings
    on seed.team_short = ratings."Team_short"
