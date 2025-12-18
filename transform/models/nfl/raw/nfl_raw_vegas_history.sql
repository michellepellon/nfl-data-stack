{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Raw Vegas Lines History

Historical snapshots of Vegas lines for CLV (Closing Line Value) analysis.
This table contains multiple snapshots per game:
- opening: Early week lines (captured Monday/Tuesday)
- closing: Pre-game lines (captured 1-2 hours before kickoff)
- interim: Any intermediate snapshots

Data source: scripts/collect_vegas_lines_snapshot.py
*/

{% set history_file = '../data/nfl/vegas_lines_history.parquet' %}

-- Check if history file exists, return empty if not
{% if execute %}
    {% set check_sql %}
        select count(*) as cnt from glob('{{ history_file }}')
    {% endset %}
    {% set result = run_query(check_sql) %}
    {% set file_exists = result.columns[0].values()[0] > 0 %}
{% else %}
    {% set file_exists = true %}
{% endif %}

{% if file_exists %}
select
    api_game_id,
    commence_time,
    home_team,
    away_team,
    bookmaker,
    snapshot_type,
    snapshot_time,
    home_moneyline,
    away_moneyline,
    home_spread,
    away_spread,
    home_win_prob_moneyline,
    home_win_prob_spread,
    home_win_prob_consensus,

    {{ add_ingestion_timestamp() }}

from read_parquet('{{ history_file }}')
{% else %}
-- Return empty table with correct schema when no history exists yet
select
    null::varchar as api_game_id,
    null::varchar as commence_time,
    null::varchar as home_team,
    null::varchar as away_team,
    null::varchar as bookmaker,
    null::varchar as snapshot_type,
    null::varchar as snapshot_time,
    null::integer as home_moneyline,
    null::integer as away_moneyline,
    null::double as home_spread,
    null::double as away_spread,
    null::double as home_win_prob_moneyline,
    null::double as home_win_prob_spread,
    null::double as home_win_prob_consensus,
    current_timestamp as ingestion_timestamp
where false
{% endif %}
