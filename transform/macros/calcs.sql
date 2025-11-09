{%- macro elo_calc(home_team, visiting_team, home_adv) -%}

   ( 1 - (1 / (10 ^ (-( {{visiting_team}} - {{home_team}} - {{home_adv}})::real/400)+1))) * 10000

{%- endmacro -%}

{%- macro elo_diff(home_team, visiting_team, result, home_adv)  -%}

   25.0 * (( {{result}} ) - (1 / (10 ^ ( - ({{visiting_team}} - {{home_team}} - {{home_adv}})::real / 400) + 1)))

{%- endmacro -%}

{%- macro mov_multiplier(point_diff, elo_diff) -%}
    /*
    Margin-of-Victory Multiplier for ELO Updates

    Formula: ln(|point_diff| + 1) * (2.2 / (|elo_diff| * 0.001 + 2.2))

    This multiplier increases ELO change for:
    - Larger point differentials (blowouts matter more)
    - Upsets (underdog wins get bigger boost)

    And decreases ELO change for:
    - Close games (1-point games are more random)
    - Expected outcomes (favorite wins as predicted)

    Based on FiveThirtyEight NFL ELO methodology
    */
    LN(ABS({{ point_diff }}) + 1) * (2.2 / (ABS({{ elo_diff }}) * 0.001 + 2.2))
{%- endmacro -%}

{%- macro elo_update(
    current_elo,
    opponent_elo,
    actual_result,
    point_diff,
    home_adv,
    k_factor
) -%}
    /*
    Complete ELO Rating Update with Margin-of-Victory

    Parameters:
    - current_elo: Team's current ELO rating
    - opponent_elo: Opponent's current ELO rating
    - actual_result: 1 for win, 0 for loss, 0.5 for tie
    - point_diff: Actual point differential (positive = team won)
    - home_adv: Home field advantage (52 for home team, 0 for away, 0 for neutral)
    - k_factor: Learning rate (default 20)

    Formula:
    new_elo = current_elo + K * MOV_mult * (actual - expected)

    Where:
    - expected = 1 / (1 + 10^(-(current_elo + home_adv - opponent_elo) / 400))
    - MOV_mult = ln(|point_diff| + 1) * (2.2 / (|elo_diff| * 0.001 + 2.2))
    */
    {{ current_elo }} +
    {{ k_factor }} *
    {{ mov_multiplier(point_diff, current_elo ~ ' + ' ~ home_adv ~ ' - ' ~ opponent_elo) }} *
    ({{ actual_result }} - (1.0 / (10.0 ^ (-({{ current_elo }} + {{ home_adv }} - {{ opponent_elo }})::real / 400.0) + 1.0)))
{%- endmacro -%}

{%- macro american_odds(value) -%}

    CASE
        WHEN {{ value }} >= 1.0 THEN '-999999'
        WHEN {{ value }} <= 0.0 THEN '+999999'
        WHEN {{ value }} >= 0.5 THEN '-' || ROUND( {{ value }} / ( 1.0 - {{ value }} ) * 100 )::int
        ELSE '+' || ((( 1.0 - {{ value }} ) / ({{ value }}::real ) * 100)::int)
    END

{%- endmacro -%}