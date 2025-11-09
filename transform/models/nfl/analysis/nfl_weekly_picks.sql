{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Weekly NFL picks formatted for presentation.
Groups predictions by confidence tier for clean, Tufte-style display.
*/

with predictions as (
    select * from {{ ref('nfl_predictions_with_features') }}
),

-- Aggregate to one row per game
game_predictions as (
    select
        week_number,
        season,
        game_id,

        -- Game teams
        max(home_team) as home_team,
        max(home_short) as home_short,
        max(visiting_team) as visiting_team,
        max(vis_short) as vis_short,

        -- Probabilities (average across simulations, though they should be identical)
        avg(home_win_prob_base) as home_win_prob_base,
        avg(home_win_prob_adjusted) as home_win_prob_adjusted,
        avg(confidence_base) as confidence_base,
        avg(confidence_adjusted) as confidence_adjusted,

        -- ELO and adjustments
        avg(elo_diff) as elo_diff,
        avg(total_adj) as total_adj,
        avg(rest_adj) as rest_adj,
        avg(temp_adj) as temp_adj,
        avg(wind_adj) as wind_adj,
        avg(injury_adj) as injury_adj,

        -- Metadata
        max(sim_count) as sim_count,
        max(include_actuals) as include_actuals

    from predictions
    where week_number is not null
    group by week_number, season, game_id
),

formatted_picks as (
    select
        week_number,
        season,
        game_id,

        -- Determine predicted winner and format matchup
        case
            when home_win_prob_adjusted > 0.5 then home_team
            else visiting_team
        end as predicted_winner,

        case
            when home_win_prob_adjusted > 0.5 then home_short
            else vis_short
        end as predicted_winner_short,

        case
            when home_win_prob_adjusted > 0.5 then vis_short
            else home_short
        end as predicted_loser_short,

        -- Format matchup string: "Winner over Loser" or "Winner @ Loser" if away
        case
            when home_win_prob_adjusted > 0.5
            then home_short || ' over ' || vis_short
            else vis_short || ' @ ' || home_short
        end as matchup,

        -- Win probability for the predicted winner
        case
            when home_win_prob_adjusted > 0.5
            then home_win_prob_adjusted
            else (1.0 - home_win_prob_adjusted)
        end as winner_probability,

        -- Game notes for context
        case
            when abs(home_win_prob_adjusted - 0.5) < 0.025 then 'Coin flip'
            when abs(home_win_prob_adjusted - 0.5) < 0.07 then 'Close game'
            when total_adj != 0 then 'Feature-adjusted'
            else ''
        end as game_notes,

        -- Upset flag (underdog winning based on ELO)
        case
            when elo_diff > 0 and home_win_prob_adjusted < 0.5 then true
            when elo_diff < 0 and home_win_prob_adjusted > 0.5 then true
            else false
        end as is_upset,

        -- Impact of adjustments
        case
            when total_adj > 20 then 'Major positive adjustment'
            when total_adj > 10 then 'Moderate positive adjustment'
            when total_adj < -20 then 'Major negative adjustment'
            when total_adj < -10 then 'Moderate negative adjustment'
            else 'Minimal adjustment'
        end as adjustment_impact,

        -- Confidence tier based on winner probability
        case
            when home_win_prob_adjusted > 0.5 then
                case
                    when home_win_prob_adjusted >= 0.75 then 'High Confidence (>75%)'
                    when home_win_prob_adjusted >= 0.60 then 'Moderate Confidence (60-75%)'
                    else 'Toss-Up (<60%)'
                end
            else
                case
                    when (1.0 - home_win_prob_adjusted) >= 0.75 then 'High Confidence (>75%)'
                    when (1.0 - home_win_prob_adjusted) >= 0.60 then 'Moderate Confidence (60-75%)'
                    else 'Toss-Up (<60%)'
                end
        end as confidence_tier,

        -- Tier sort order
        case
            when home_win_prob_adjusted > 0.5 then
                case
                    when home_win_prob_adjusted >= 0.75 then 1
                    when home_win_prob_adjusted >= 0.60 then 2
                    else 3
                end
            else
                case
                    when (1.0 - home_win_prob_adjusted) >= 0.75 then 1
                    when (1.0 - home_win_prob_adjusted) >= 0.60 then 2
                    else 3
                end
        end as tier_order,

        -- Individual components for detailed view
        home_team,
        home_short,
        visiting_team,
        vis_short,
        home_win_prob_base,
        home_win_prob_adjusted,
        confidence_base,
        confidence_adjusted,
        elo_diff,
        total_adj,

        -- Feature details
        rest_adj,
        temp_adj,
        wind_adj,
        injury_adj,

        -- Simulation metadata
        sim_count,
        include_actuals,

        {{ add_ingestion_timestamp() }}

    from game_predictions
)

select * from formatted_picks
order by week_number, tier_order, winner_probability desc
