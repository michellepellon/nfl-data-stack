/*
NFL Bye Week Tracking

Identifies each team's bye week and flags games where teams are coming off a bye.
Bye weeks are determined by finding weeks where a team doesn't appear in the schedule.
*/

with all_teams as (
    select distinct team
    from {{ ref('nfl_ratings') }}
),

all_weeks as (
    select distinct week as week_number
    from {{ ref('nfl_raw_schedule') }}
    where week <= 18  -- Regular season only
),

team_schedule as (
    select
        week as week_number,
        vistm as team
    from {{ ref('nfl_raw_schedule') }}
    where week <= 18

    union all

    select
        week as week_number,
        hometm as team
    from {{ ref('nfl_raw_schedule') }}
    where week <= 18
),

team_bye_weeks as (
    select
        t.team,
        w.week_number as bye_week
    from all_teams t
    cross join all_weeks w
    left join team_schedule ts
        on ts.team = t.team
        and ts.week_number = w.week_number
    where ts.team is null  -- Week where team doesn't appear = bye week
        and w.week_number between 5 and 14  -- Bye weeks typically occur weeks 5-14
),

games_after_bye as (
    select
        s.id as game_id,
        s.week as week_number,
        s.hometm as home_team,
        s.vistm as visiting_team,
        case
            when hb.bye_week = s.week - 1 then 1
            else 0
        end as home_team_off_bye,
        case
            when vb.bye_week = s.week - 1 then 1
            else 0
        end as visiting_team_off_bye,
        {{ add_ingestion_timestamp() }}
    from {{ ref('nfl_raw_schedule') }} s
    left join team_bye_weeks hb
        on hb.team = s.hometm
    left join team_bye_weeks vb
        on vb.team = s.vistm
    where s.week <= 18
)

select * from games_after_bye
