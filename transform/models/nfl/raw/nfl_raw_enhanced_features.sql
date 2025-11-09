select
    game_id,
    season,
    week,
    home_team,
    away_team,
    home_rest,
    away_rest,
    rest_diff,
    roof,
    temp,
    wind,
    stadium_id,
    stadium,
    home_injury_score,
    away_injury_score,
    injury_diff,
    {{ add_ingestion_timestamp() }}
from {{ source("nfl", "nfl_enhanced_features") }}
