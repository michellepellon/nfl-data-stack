select
    team,
    win_total,
    {{ add_ingestion_timestamp() }}
from {{ ref("nfl_ratings") }}
group by all
