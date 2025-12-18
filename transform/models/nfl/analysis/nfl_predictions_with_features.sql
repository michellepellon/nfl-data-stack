{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Enhanced prediction view combining ELO predictions with feature adjustments.
Designed for Tufte-style dashboards: information-dense, minimal chartjunk.
*/

with predictions as (
    select * from {{ ref('nfl_reg_season_predictions') }}
),

adjustments as (
    select * from {{ ref('nfl_elo_adjustments') }}
),

recent_form as (
    select * from {{ ref('nfl_recent_form') }}
),

vegas_lines as (
    select * from {{ ref('nfl_vegas_lines') }}
),

dynamic_weights as (
    select * from {{ ref('nfl_dynamic_weights') }}
),

ratings as (
    select
        team,
        team_short,
        conf,
        division,
        elo_rating,
        original_rating,
        elo_rating - original_rating as season_delta
    from {{ ref('nfl_ratings') }}
)

select
    -- Game identifiers
    p.game_id,
    p.week_number,
    p.type as game_type,

    -- Home team
    p.home_team,
    p.home_short,
    home_ratings.conf as home_conf,
    home_ratings.division as home_div,
    p.home_team_elo_rating,
    home_ratings.season_delta as home_elo_delta,

    -- Visiting team
    p.visiting_team,
    p.vis_short,
    vis_ratings.conf as vis_conf,
    vis_ratings.division as vis_div,
    p.visiting_team_elo_rating,
    vis_ratings.season_delta as vis_elo_delta,

    -- Base prediction (no features)
    p.elo_diff,
    p.home_team_win_probability / 10000.0 as home_win_prob_base,
    (10000 - p.home_team_win_probability) / 10000.0 as away_win_prob_base,
    p.american_odds as odds_american,

    -- Feature adjustments
    coalesce(adj.rest_adjustment, 0) as rest_adj,
    coalesce(adj.temp_adjustment, 0) as temp_adj,
    coalesce(adj.wind_adjustment, 0) as wind_adj,
    coalesce(adj.weather_adjustment, 0) as weather_adj,
    coalesce(adj.injury_adjustment, 0) as injury_adj,
    coalesce(adj.total_adjustment, 0) as total_adj,

    -- Momentum adjustments (recent form)
    coalesce(home_form.total_momentum_adjustment, 0) as home_momentum_adj,
    coalesce(away_form.total_momentum_adjustment, 0) as away_momentum_adj,
    coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) as momentum_diff,

    -- Feature metadata (for explanatory tooltips)
    adj.rest_diff as rest_days_diff,
    adj.roof as roof_type,
    adj.temp as temperature,
    adj.wind as wind_speed,
    adj.home_injury_score,
    adj.away_injury_score,
    adj.injury_diff,

    -- Adjusted ELO difference and probability
    -- (Adjustment is added to home advantage, affecting effective ELO diff)
    p.elo_diff + coalesce(adj.total_adjustment, 0) + coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) as elo_diff_adjusted,

    -- Calculate adjusted win probability using logistic function
    -- P(home wins) = 1 / (1 + 10^(-(elo_diff_adjusted + home_adv) / 400))
    -- Using standard 52 home advantage
    -- Now includes: contextual features + momentum
    1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) + 52) / 400.0))) as home_win_prob_adjusted,

    -- Predicted winner
    p.winning_team,
    case
        when (1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) + 52) / 400.0)))) > 0.5
        then p.home_team
        else p.visiting_team
    end as predicted_winner_adjusted,

    -- Prediction confidence (distance from 50%)
    abs((p.home_team_win_probability / 10000.0) - 0.5) * 2 as confidence_base,
    abs((1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) + 52) / 400.0)))) - 0.5) * 2 as confidence_adjusted,

    -- Vegas lines
    vegas.home_spread,
    vegas.home_moneyline,
    vegas.home_win_prob_consensus as vegas_home_win_prob,

    -- Dynamic ensemble weights (based on rolling 4-week performance)
    -- Defaults to 0.5/0.5 during cold start or when weights unavailable
    coalesce(dw.elo_weight, 0.5) as elo_weight,
    coalesce(dw.vegas_weight, 0.5) as vegas_weight,
    coalesce(dw.is_cold_start, true) as weights_cold_start,

    -- Ensemble prediction (dynamic weighted average of ELO + momentum and Vegas)
    -- Uses performance-based weights instead of fixed 50/50
    case
        when vegas.home_win_prob_consensus is not null then
            coalesce(dw.elo_weight, 0.5) * (1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) + 52) / 400.0)))) +
            coalesce(dw.vegas_weight, 0.5) * vegas.home_win_prob_consensus
        else
            1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) + 52) / 400.0)))
    end as home_win_prob_ensemble,

    -- Ensemble predicted winner
    case
        when vegas.home_win_prob_consensus is not null then
            case
                when (coalesce(dw.elo_weight, 0.5) * (1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) + 52) / 400.0)))) + coalesce(dw.vegas_weight, 0.5) * vegas.home_win_prob_consensus) > 0.5
                then p.home_team
                else p.visiting_team
            end
        else
            case
                when (1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) + 52) / 400.0)))) > 0.5
                then p.home_team
                else p.visiting_team
            end
    end as predicted_winner_ensemble,

    -- Ensemble confidence
    abs(
        case
            when vegas.home_win_prob_consensus is not null then
                (coalesce(dw.elo_weight, 0.5) * (1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) + 52) / 400.0)))) + coalesce(dw.vegas_weight, 0.5) * vegas.home_win_prob_consensus)
            else
                (1.0 / (1.0 + power(10, -((p.elo_diff + coalesce(adj.total_adjustment, 0) + coalesce(home_form.total_momentum_adjustment, 0) - coalesce(away_form.total_momentum_adjustment, 0) + 52) / 400.0))))
        end - 0.5
    ) * 2 as confidence_ensemble,

    -- Simulation metadata
    p.occurances as sim_count,
    p.include_actuals,

    {{ add_ingestion_timestamp() }}

from predictions p
left join adjustments adj
    on p.week_number = adj.week
    and p.home_short = adj.home_team
    and p.vis_short = adj.away_team
left join recent_form home_form
    on p.week_number = home_form.week_number
    and p.home_team = home_form.team
    and p.type = 'reg_season'  -- Only for regular season
left join recent_form away_form
    on p.week_number = away_form.week_number
    and p.visiting_team = away_form.team
    and p.type = 'reg_season'  -- Only for regular season
left join ratings home_ratings on p.home_team = home_ratings.team
left join ratings vis_ratings on p.visiting_team = vis_ratings.team
left join vegas_lines vegas
    on p.week_number = vegas.week_number
    and p.home_team = vegas.home_team
    and p.visiting_team = vegas.visiting_team
left join dynamic_weights dw
    on p.week_number = dw.week_number
