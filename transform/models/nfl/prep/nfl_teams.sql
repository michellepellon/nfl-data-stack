select
    team as team,
    team_short,
    {{ add_ingestion_timestamp() }}
from {{ ref("nfl_ratings") }}
group by all
