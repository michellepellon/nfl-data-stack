select
    season,
    week as wk,
    "Date" as game_date,
    "Winner/tie" as winner,
    ptsw as winner_pts,
    "Loser/tie" as loser,
    ptsl as loser_pts,
    case when ptsl = ptsw then 1 else 0 end as tie_flag,
    "@" as at_symbol,
    -- Turnover data (may be null if not collected)
    tow as winner_turnovers,
    tol as loser_turnovers,
    ydsw as winner_yards,
    ydsl as loser_yards,
    {{ add_ingestion_timestamp() }}
from {{ source("nfl", "nfl_results") }}
