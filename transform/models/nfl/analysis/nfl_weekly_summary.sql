{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Weekly summary statistics for NFL predictions.
Shows key insights: most confident picks, biggest upsets, feature impact.
*/

with picks as (
    select * from {{ ref('nfl_weekly_picks') }}
),

weekly_stats as (
    select
        week_number,
        season,

        -- Game counts by confidence
        count(*) as total_games,
        count(case when confidence_tier = 'High Confidence (>75%)' then 1 end) as high_confidence_count,
        count(case when confidence_tier = 'Moderate Confidence (60-75%)' then 1 end) as moderate_confidence_count,
        count(case when confidence_tier = 'Toss-Up (<60%)' then 1 end) as tossup_count,

        -- Coin flip and close games
        count(case when game_notes = 'Coin flip' then 1 end) as coin_flip_games,
        count(case when game_notes = 'Close game' then 1 end) as close_games,

        -- Upset picks
        count(case when is_upset then 1 end) as upset_picks,

        -- Feature impact
        count(case when total_adj != 0 then 1 end) as feature_adjusted_games,
        avg(case when total_adj != 0 then total_adj end) as avg_feature_adjustment,
        max(abs(total_adj)) as max_feature_impact,

        -- Probability ranges
        avg(winner_probability) as avg_win_probability,
        min(winner_probability) as min_win_probability,
        max(winner_probability) as max_win_probability,

        -- Most confident pick details
        max(case when winner_probability = (select max(winner_probability) from picks p2 where p2.week_number = picks.week_number)
            then matchup end) as most_confident_pick,
        max(case when winner_probability = (select max(winner_probability) from picks p2 where p2.week_number = picks.week_number)
            then winner_probability end) as most_confident_prob,

        -- Closest game details
        max(case when winner_probability = (select min(winner_probability) from picks p2 where p2.week_number = picks.week_number)
            then matchup end) as closest_game,
        max(case when winner_probability = (select min(winner_probability) from picks p2 where p2.week_number = picks.week_number)
            then winner_probability end) as closest_game_prob,

        {{ add_ingestion_timestamp() }}

    from picks
    group by week_number, season
)

select * from weekly_stats
order by season, week_number
