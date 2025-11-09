select
    *,
    {{ add_ingestion_timestamp() }}
from {{ source("nfl", "nfl_schedule") }}
