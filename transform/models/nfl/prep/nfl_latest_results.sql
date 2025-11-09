with
    cte_inner as (
        select
            row_number() over (order by r.season, r.wk, r.winner, r.loser) as game_id,
            r.wk as week_number,
            case
                when r.at_symbol = '@' then r.loser  -- @ means winner is away, loser is home
                else r.winner  -- no @ means winner is home
            end as home_team,
            case
                when r.at_symbol = '@' then r.loser_pts
                else r.winner_pts
            end as home_team_score,
            case
                when r.at_symbol = '@' then r.winner  -- @ means winner is away
                else r.loser  -- no @ means loser is away
            end as visiting_team,
            case
                when r.at_symbol = '@' then r.winner_pts
                else r.loser_pts
            end as visiting_team_score,
            r.winner as winning_team,
            r.loser as losing_team,
            {{ var("include_actuals") }} as include_actuals,
            coalesce(s.neutral, 0) as neutral_site,
            r.winner_pts - r.loser_pts as margin
        from {{ ref("nfl_raw_results") }} r
        left join {{ ref("nfl_raw_schedule") }} s
            on s.week = r.wk
            and s.hometm = case when r.at_symbol = '@' then r.loser else r.winner end
            and s.vistm = case when r.at_symbol = '@' then r.winner else r.loser end
        where r.winner is not null and r.loser is not null
    ),
    cte_outer as (
        select
            *,
            case
                when visiting_team_score > home_team_score
                then 1
                when visiting_team_score = home_team_score
                then 0.5
                else 0
            end as game_result,
            abs(visiting_team_score - home_team_score) as margin
        from cte_inner
    )
select
    *,
    {{ add_ingestion_timestamp() }}
from cte_outer
