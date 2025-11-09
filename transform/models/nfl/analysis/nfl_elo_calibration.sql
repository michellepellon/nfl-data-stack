/*
ELO Calibration Validation

Validates that ELO win probabilities are well-calibrated by comparing
predicted probabilities to actual outcomes.

Key Metrics:
1. Calibration Curve: Predicted vs Actual win rates by probability bin
2. Brier Score: Mean squared error of probability predictions (lower is better)
3. Log Loss: Penalizes confident wrong predictions
4. Calibration Error: Average absolute difference between predicted and actual

A well-calibrated model has:
- Brier Score < 0.25 (random baseline)
- Calibration curve close to y=x diagonal
- Small calibration error (<5%)
*/

with
    -- Get all completed games with predictions from ELO rollforward
    games_with_predictions as (
        select
            game_id,
            home_team,
            visiting_team,
            winning_team,
            margin,

            -- Extract home team win probability from rollforward
            -- The elo_rollforward stores predictions at time of game
            home_team_elo_rating as home_elo,
            visiting_team_elo_rating as visiting_elo,

            -- Calculate home team win probability
            -- This replicates the prediction made before the game
            1.0 / (1.0 + power(10.0, -(home_team_elo_rating - visiting_team_elo_rating + {{ var("nfl_elo_offset") }})::real / 400.0)) as predicted_home_win_prob,

            -- Actual outcome (1 if home won, 0 if away won)
            case
                when winning_team = home_team then 1.0
                when winning_team = visiting_team then 0.0
                else 0.5  -- tie
            end as actual_home_win

        from {{ ref("nfl_elo_rollforward") }}
        where winning_team is not null  -- exclude ties for now
    ),

    -- Create probability bins for calibration curve
    binned_predictions as (
        select
            game_id,
            home_team,
            visiting_team,
            winning_team,
            predicted_home_win_prob,
            actual_home_win,

            -- Bin predictions into 10% buckets
            case
                when predicted_home_win_prob < 0.1 then '00-10%'
                when predicted_home_win_prob < 0.2 then '10-20%'
                when predicted_home_win_prob < 0.3 then '20-30%'
                when predicted_home_win_prob < 0.4 then '30-40%'
                when predicted_home_win_prob < 0.5 then '40-50%'
                when predicted_home_win_prob < 0.6 then '50-60%'
                when predicted_home_win_prob < 0.7 then '60-70%'
                when predicted_home_win_prob < 0.8 then '70-80%'
                when predicted_home_win_prob < 0.9 then '80-90%'
                else '90-100%'
            end as probability_bin,

            -- Bin lower bound for plotting
            floor(predicted_home_win_prob * 10) * 10 as bin_lower,

            -- Squared error for Brier score
            power(predicted_home_win_prob - actual_home_win, 2) as squared_error,

            -- Log loss component
            case
                when actual_home_win = 1.0
                then -ln(predicted_home_win_prob)
                else -ln(1.0 - predicted_home_win_prob)
            end as log_loss_component

        from games_with_predictions
    ),

    -- Calculate calibration metrics per bin
    calibration_by_bin as (
        select
            probability_bin,
            bin_lower,
            count(*) as n_games,
            avg(predicted_home_win_prob) as avg_predicted_prob,
            avg(actual_home_win) as actual_win_rate,
            abs(avg(predicted_home_win_prob) - avg(actual_home_win)) as calibration_error,
            avg(squared_error) as bin_brier_score,
            stddev(actual_home_win) as actual_stddev

        from binned_predictions
        group by probability_bin, bin_lower
        having count(*) >= 3  -- require at least 3 games per bin
    ),

    -- Pre-calculate mean for R² calculation
    actual_mean as (
        select avg(actual_home_win) as mean_actual
        from binned_predictions
    ),

    -- Calculate overall metrics
    overall_metrics as (
        select
            count(*) as total_games,
            avg(squared_error) as brier_score,
            avg(log_loss_component) as log_loss,
            avg(abs(predicted_home_win_prob - actual_home_win)) as mean_absolute_error,
            stddev(predicted_home_win_prob - actual_home_win) as prediction_stddev,

            -- Calculate R² for calibration curve
            -- R² = 1 - (SS_res / SS_tot)
            -- SS_res = sum((actual - predicted)²)
            -- SS_tot = sum((actual - mean(actual))²)
            1.0 - (
                sum(power(bp.actual_home_win - bp.predicted_home_win_prob, 2)) /
                nullif(sum(power(bp.actual_home_win - am.mean_actual, 2)), 0)
            ) as calibration_r_squared

        from binned_predictions bp
        cross join actual_mean am
    )

select
    -- Bin-level calibration data
    cb.probability_bin,
    cb.bin_lower,
    cb.bin_lower + 10 as bin_upper,
    cb.n_games,
    round(cb.avg_predicted_prob * 100, 1) as avg_predicted_pct,
    round(cb.actual_win_rate * 100, 1) as actual_win_rate_pct,
    round(cb.calibration_error * 100, 1) as calibration_error_pct,
    round(cb.bin_brier_score, 4) as bin_brier_score,

    -- Overall metrics (repeated for each row for easy access)
    om.total_games,
    round(om.brier_score, 4) as overall_brier_score,
    round(om.log_loss, 4) as overall_log_loss,
    round(om.mean_absolute_error * 100, 1) as overall_mae_pct,
    round(om.calibration_r_squared, 4) as calibration_r_squared,

    -- Quality assessment
    case
        when cb.calibration_error < 0.05 then 'Excellent'
        when cb.calibration_error < 0.10 then 'Good'
        when cb.calibration_error < 0.15 then 'Fair'
        else 'Poor'
    end as bin_calibration_quality,

    -- Display strings
    cb.probability_bin || ': '
    || round(cb.avg_predicted_prob * 100, 1)::text || '% predicted, '
    || round(cb.actual_win_rate * 100, 1)::text || '% actual ('
    || cb.n_games::text || ' games)' as calibration_summary,

    {{ add_ingestion_timestamp() }}

from calibration_by_bin cb
cross join overall_metrics om
order by cb.bin_lower
