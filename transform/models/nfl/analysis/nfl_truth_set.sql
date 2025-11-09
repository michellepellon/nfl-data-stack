{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Truth Set Definition with Proper Time Cutoffs

Defines what data is "knowable" at prediction time to prevent data leakage.
Critical for proper model evaluation and backtesting.

Key Principles:
1. Data cutoff = kickoff time (no future information)
2. Only use information available BEFORE the game starts
3. Store exact feature state at prediction time
4. Handle time zones consistently (all times in ET)

Fields tracked:
- Game outcome (winner, score)
- Features available at kickoff
- Prediction timestamp
- Data lineage
*/

with raw_schedule as (
    select
        id as game_id,
        week as week_number,
        day,
        date,
        hometm as home_team,
        vistm as visiting_team,
        neutral as neutral_site
    from {{ ref('nfl_raw_schedule') }}
),

schedule as (
    select
        s.game_id,
        s.week_number,
        sched.type as game_type,
        s.home_team,
        s.visiting_team,
        s.neutral_site,
        s.date as game_date,
        s.day,
        -- Normalize all game times to ET
        -- NFL games typically start at 1pm, 4pm, or 8pm ET on Sunday
        case
            when s.day = 'Sunday' and s.week_number <= 18 then
                -- Assume 1pm ET start for most Sunday games
                s.date || ' 13:00:00'
            when s.day = 'Thursday' then
                -- Thursday Night Football at 8:20pm ET
                s.date || ' 20:20:00'
            when s.day = 'Monday' then
                -- Monday Night Football at 8:15pm ET
                s.date || ' 20:15:00'
            when s.day = 'Saturday' then
                -- Saturday games at 4:30pm or 8:15pm ET
                s.date || ' 16:30:00'
            else
                -- Default to 1pm ET
                s.date || ' 13:00:00'
        end as kickoff_timestamp_et
    from raw_schedule s
    left join {{ ref('nfl_schedules') }} sched
        on s.week_number = sched.week_number
        and s.home_team = sched.home_team
        and s.visiting_team = sched.visiting_team
    where sched.type = 'reg_season' or sched.type is null
),

results as (
    select
        game_id,
        week_number,
        home_team,
        visiting_team,
        home_team_score,
        visiting_team_score,
        winning_team,
        losing_team,
        margin,
        game_result,
        neutral_site
    from {{ ref('nfl_latest_results') }}
    where week_number is not null
      and winning_team is not null
),

-- Features available at kickoff time
features_at_kickoff as (
    select
        game_id,
        week,
        home_team,
        away_team,
        home_rest,
        away_rest,
        rest_diff,
        roof,
        temp,
        wind,
        home_injury_score,
        away_injury_score,
        injury_diff
    from {{ ref('nfl_raw_enhanced_features') }}
),

-- ELO ratings before the game (no contamination from game outcome)
elo_ratings_pre_game as (
    select
        team,
        team_short,
        elo_rating,
        original_rating,
        elo_rating - original_rating as season_delta
    from {{ ref('nfl_ratings') }}
),

-- Combine into truth set
truth_set as (
    select
        -- Game identifiers
        s.game_id,
        s.week_number,
        s.game_type,
        s.kickoff_timestamp_et,

        -- Teams
        s.home_team,
        s.visiting_team,
        s.neutral_site,

        -- Ground truth (outcome)
        r.home_team_score,
        r.visiting_team_score,
        r.winning_team,
        r.losing_team,
        r.margin,
        case when r.winning_team = s.home_team then 1 else 0 end as home_team_won,

        -- Features available at kickoff (no leakage)
        f.home_rest,
        f.away_rest,
        f.rest_diff,
        f.roof,
        f.temp,
        f.wind,
        f.home_injury_score,
        f.away_injury_score,
        f.injury_diff,

        -- ELO ratings before game
        home_elo.elo_rating as home_elo_pre_game,
        away_elo.elo_rating as away_elo_pre_game,
        home_elo.elo_rating - away_elo.elo_rating as elo_diff_pre_game,

        -- Data lineage
        'nfl_schedules' as schedule_source,
        'nfl_latest_results' as outcome_source,
        'nfl_raw_enhanced_features' as features_source,
        'nfl_ratings' as elo_source,

        -- Validation flags
        case when r.game_id is null then true else false end as missing_outcome,
        case when f.game_id is null then true else false end as missing_features,
        case when s.kickoff_timestamp_et::timestamp <= current_timestamp then true else false end as game_completed,

        {{ add_ingestion_timestamp() }}

    from schedule s
    left join results r
        on s.week_number = r.week_number
        and s.home_team = r.home_team
        and s.visiting_team = r.visiting_team
    left join features_at_kickoff f
        on s.week_number = f.week
        and s.home_team = f.home_team
        and s.visiting_team = f.away_team
    left join elo_ratings_pre_game home_elo
        on s.home_team = home_elo.team
    left join elo_ratings_pre_game away_elo
        on s.visiting_team = away_elo.team
)

select
    *,
    -- Quality checks
    case
        when missing_outcome and game_completed then 'Missing outcome for completed game'
        when missing_features then 'Missing feature data'
        when home_elo_pre_game is null then 'Missing home ELO'
        when away_elo_pre_game is null then 'Missing away ELO'
        else 'OK'
    end as data_quality_status

from truth_set
where week_number is not null
order by week_number, game_id
