{{
    config(
        materialized='external',
        format='parquet'
    )
}}

/*
Playoff Probability Confidence Intervals

Calculates point estimates and 95% confidence intervals for playoff metrics using
the Monte Carlo simulation distribution (10,000 scenarios per team).

Methodology:
- Point estimate: proportion of scenarios where event occurs
- Confidence interval: Wilson score interval for binomial proportions
- Wilson CI is more accurate than normal approximation for proportions near 0 or 1

Alternative: Use simulation percentiles as empirical confidence bounds
- This treats the MC distribution as the sampling distribution
- 95% CI = [2.5th percentile, 97.5th percentile] of playoff outcomes across scenarios

We use the empirical percentile method since we already have 10,000 MC scenarios.
*/

with
    -- Calculate point estimates from Monte Carlo scenarios
    point_estimates as (
        select
            winning_team as team,
            conf,
            -- Playoff probability (proportion of scenarios making playoffs)
            avg(made_playoffs::float) as playoff_prob,
            avg(first_round_bye::float) as bye_prob,
            avg(wins) as avg_wins,
            avg(season_rank) as avg_seed,
            count(*) as n_scenarios
        from {{ ref("nfl_reg_season_end") }}
        group by winning_team, conf
    ),

    -- Calculate empirical percentiles for confidence intervals
    percentile_bounds as (
        select
            winning_team as team,

            -- Win distribution percentiles
            percentile_cont(0.025) within group (order by wins) as wins_ci_lower,
            percentile_cont(0.975) within group (order by wins) as wins_ci_upper,

            -- Seed distribution percentiles
            percentile_cont(0.025) within group (order by season_rank) as seed_ci_lower,
            percentile_cont(0.975) within group (order by season_rank) as seed_ci_upper,

            -- For binary outcomes (made_playoffs, first_round_bye),
            -- calculate SE using binomial formula then construct CI
            avg(made_playoffs::float) as p_playoff,
            avg(first_round_bye::float) as p_bye,
            count(*) as n

        from {{ ref("nfl_reg_season_end") }}
        group by winning_team
    ),

    -- Calculate Wilson score confidence intervals for binary proportions
    wilson_ci as (
        select
            team,
            p_playoff,
            p_bye,
            n,

            -- Wilson score CI for playoff probability
            -- Formula: (p + z²/2n ± z√(p(1-p)/n + z²/4n²)) / (1 + z²/n)
            -- For 95% CI, z = 1.96
            (
                p_playoff + (1.96 * 1.96) / (2.0 * n)
                - 1.96 * sqrt(p_playoff * (1 - p_playoff) / n + (1.96 * 1.96) / (4.0 * n * n))
            ) / (1 + (1.96 * 1.96) / n) as playoff_ci_lower,

            (
                p_playoff + (1.96 * 1.96) / (2.0 * n)
                + 1.96 * sqrt(p_playoff * (1 - p_playoff) / n + (1.96 * 1.96) / (4.0 * n * n))
            ) / (1 + (1.96 * 1.96) / n) as playoff_ci_upper,

            -- Wilson score CI for bye probability
            (
                p_bye + (1.96 * 1.96) / (2.0 * n)
                - 1.96 * sqrt(p_bye * (1 - p_bye) / n + (1.96 * 1.96) / (4.0 * n * n))
            ) / (1 + (1.96 * 1.96) / n) as bye_ci_lower,

            (
                p_bye + (1.96 * 1.96) / (2.0 * n)
                + 1.96 * sqrt(p_bye * (1 - p_bye) / n + (1.96 * 1.96) / (4.0 * n * n))
            ) / (1 + (1.96 * 1.96) / n) as bye_ci_upper

        from percentile_bounds
    )

select
    pe.team,
    pe.conf,
    r.elo_rating,

    -- Playoff probability with Wilson CI
    round(pe.playoff_prob * 100, 1) as playoff_prob_pct,
    round(wc.playoff_ci_lower * 100, 1) as playoff_ci_lower_pct,
    round(wc.playoff_ci_upper * 100, 1) as playoff_ci_upper_pct,
    round((wc.playoff_ci_upper - wc.playoff_ci_lower) * 100, 1) as playoff_ci_width_pct,

    -- First round bye probability with Wilson CI
    round(pe.bye_prob * 100, 1) as bye_prob_pct,
    round(wc.bye_ci_lower * 100, 1) as bye_ci_lower_pct,
    round(wc.bye_ci_upper * 100, 1) as bye_ci_upper_pct,
    round((wc.bye_ci_upper - wc.bye_ci_lower) * 100, 1) as bye_ci_width_pct,

    -- Average wins with empirical percentile CI
    round(pe.avg_wins, 1) as avg_wins,
    round(pb.wins_ci_lower, 1) as wins_ci_lower,
    round(pb.wins_ci_upper, 1) as wins_ci_upper,
    round(pb.wins_ci_upper - pb.wins_ci_lower, 1) as wins_ci_width,

    -- Average seed with empirical percentile CI
    round(pe.avg_seed, 1) as avg_seed,
    round(pb.seed_ci_lower, 1) as seed_ci_lower,
    round(pb.seed_ci_upper, 1) as seed_ci_upper,

    -- Formatted display strings
    round(pe.playoff_prob * 100, 1)::text
    || '% ['
    || round(wc.playoff_ci_lower * 100, 1)::text
    || '% - '
    || round(wc.playoff_ci_upper * 100, 1)::text
    || '%]' as playoff_prob_display,

    round(pe.bye_prob * 100, 1)::text
    || '% ['
    || round(wc.bye_ci_lower * 100, 1)::text
    || '% - '
    || round(wc.bye_ci_upper * 100, 1)::text
    || '%]' as bye_prob_display,

    round(pe.avg_wins, 1)::text
    || ' ['
    || round(pb.wins_ci_lower, 1)::text
    || ' - '
    || round(pb.wins_ci_upper, 1)::text
    || ']' as wins_display,

    round(pe.avg_seed, 1)::text
    || ' ['
    || round(pb.seed_ci_lower, 1)::text
    || ' - '
    || round(pb.seed_ci_upper, 1)::text
    || ']' as seed_display,

    pe.n_scenarios,
    {{ var("sim_start_game_id") }} as sim_start_game_id,
    {{ add_ingestion_timestamp() }}

from point_estimates pe
left join percentile_bounds pb on pb.team = pe.team
left join wilson_ci wc on wc.team = pe.team
left join {{ ref("nfl_ratings") }} r on r.team = pe.team
order by pe.playoff_prob desc
