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
    -- QB-specific injury scores (0.0 fallback when columns not present)
    -- These columns are added by the updated collect_enhanced_features.py script
    0.0 as home_qb_injury_score,
    0.0 as away_qb_injury_score,
    0.0 as qb_injury_diff,
    0.0 as home_non_qb_injury_score,
    0.0 as away_non_qb_injury_score,
    0.0 as non_qb_injury_diff,
    {{ add_ingestion_timestamp() }}
from {{ source("nfl", "nfl_enhanced_features") }}
