"""
ELO Rating Rollforward with Margin-of-Victory Updates

This model calculates updated ELO ratings for each team after each completed game,
incorporating margin-of-victory multipliers for more accurate rating adjustments.

Algorithm:
1. Start with initial ratings from nfl_raw_team_ratings
2. Process games in chronological order (by game_id)
3. For each game:
   a. Calculate expected win probabilities using current ELO ratings
   b. Apply actual result (1=away win, 0=home win, 0.5=tie)
   c. Calculate MOV multiplier: ln(|margin|+1) * (2.2 / (|elo_diff| * 0.001 + 2.2))
   d. Update ELO: elo_change = K * MOV_mult * (actual - expected)
   e. Apply changes: home_elo -= elo_change, away_elo += elo_change
4. Store pre-game ratings and elo_change for each game

Based on FiveThirtyEight NFL ELO methodology:
https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/
"""

import pandas as pd
import math

def calc_elo_diff(
    game_result: float,
    home_elo: float,
    visiting_elo: float,
    home_adv: float,
    scoring_margin: float,
    contextual_adjustment: float = 0.0,
    k_factor: float = 20.0,
    elo_scale: float = 400.0,
    mov_multiplier_base: float = 2.2,
    mov_multiplier_divisor: float = 0.001
) -> float:
    """
    Calculate ELO rating change with Margin-of-Victory multiplier and contextual adjustments

    Parameters:
    - game_result: 1 if visiting team won, 0 if home team won, 0.5 for tie
    - home_elo: Home team's current ELO rating
    - visiting_elo: Visiting team's current ELO rating
    - home_adv: Home field advantage (typically 48 points)
    - scoring_margin: Absolute point differential
    - contextual_adjustment: Travel/altitude/primetime adjustment (negative hurts away team)
    - k_factor: Learning rate (default 20)
    - elo_scale: ELO rating scale (default 400, where 400-point diff = 90% win prob)
    - mov_multiplier_base: MOV multiplier base constant (default 2.2, FiveThirtyEight formula)
    - mov_multiplier_divisor: MOV multiplier elo_diff adjustment factor (default 0.001)

    Returns:
    - ELO change (positive = visiting team gains rating, negative = home team gains)

    Formula:
    elo_change = K * MOV_mult * (actual - expected)

    Where:
    - expected = 1 / (1 + 10^(-(visiting_elo - home_elo - home_adv - contextual_adj) / elo_scale))
    - MOV_mult = ln(|margin|+1) * (mov_base / (|elo_diff| * mov_div + mov_base))
    - elo_diff = winner_elo - loser_elo (accounts for upset magnitude)
    """
    # Convert to float to avoid type issues
    game_result = float(game_result)
    home_elo = float(home_elo)
    visiting_elo = float(visiting_elo)
    home_adv = float(home_adv)
    scoring_margin = float(scoring_margin)
    contextual_adjustment = float(contextual_adjustment) if contextual_adjustment is not None else 0.0
    k_factor = float(k_factor)
    elo_scale = float(elo_scale)
    mov_multiplier_base = float(mov_multiplier_base)
    mov_multiplier_divisor = float(mov_multiplier_divisor)

    # Adjusted home ELO (includes home field advantage and contextual adjustments)
    # contextual_adjustment is negative when it hurts the away team, so we subtract it
    # This effectively adds to home team's advantage
    adj_home_elo = home_elo + home_adv - contextual_adjustment

    # Calculate ELO differential from winner's perspective
    # If visiting team won (game_result=1): visiting_elo - adj_home_elo
    # If home team won (game_result=0): adj_home_elo - visiting_elo
    winner_elo_diff = visiting_elo - adj_home_elo if game_result == 1 else adj_home_elo - visiting_elo

    # Margin-of-Victory multiplier (FiveThirtyEight formula)
    # - Larger margins increase the multiplier (blowouts matter more)
    # - Upsets (negative winner_elo_diff) increase the multiplier
    # - Close games between similar teams have multiplier near 1.0
    margin_of_victory_multiplier = math.log(abs(scoring_margin) + 1) * (
        mov_multiplier_base / (winner_elo_diff * mov_multiplier_divisor + mov_multiplier_base)
    )

    # Expected win probability for visiting team (includes contextual adjustments)
    expected_visiting_win = 1.0 / (10.0 ** (-(visiting_elo - home_elo - home_adv + contextual_adjustment) / elo_scale) + 1.0)

    # ELO change (from home team's perspective, negative means home team gains rating)
    # game_result: 1 = visiting team won, 0 = home team won
    elo_change = k_factor * (game_result - expected_visiting_win) * margin_of_victory_multiplier

    return elo_change

def model(dbt, sess):
    """
    dbt Python model to calculate ELO rating rollforward

    Returns a DataFrame with one row per completed game showing:
    - Pre-game ELO ratings for both teams
    - ELO change amount
    - Margin of victory
    - Timestamp of ingestion
    """
    # Get configuration parameters
    home_adv = dbt.config.get("nfl_elo_offset", 52.0)
    k_factor = dbt.config.get("elo_k_factor", 20.0)
    elo_scale = dbt.config.get("elo_scale", 400.0)
    mov_multiplier_base = dbt.config.get("mov_multiplier_base", 2.2)
    mov_multiplier_divisor = dbt.config.get("mov_multiplier_divisor", 0.001)

    # Load initial ELO ratings
    team_ratings = dbt.ref("nfl_raw_team_ratings").df()
    original_elo = dict(zip(team_ratings["team"], team_ratings["elo_rating"].astype(float)))
    working_elo = original_elo.copy()

    # Load completed games in chronological order
    nfl_elo_latest = (dbt.ref("nfl_latest_results")
        .project("game_id, visiting_team, home_team, winning_team, game_result, neutral_site, margin")
        .order("game_id")
    )
    nfl_elo_latest.execute()

    # Load contextual adjustments (travel, altitude, primetime)
    try:
        contextual_adjustments = dbt.ref("nfl_travel_primetime").df()
        contextual_dict = dict(zip(
            contextual_adjustments["game_id"],
            contextual_adjustments["total_contextual_adjustment"].fillna(0.0)
        ))
    except Exception:
        # If contextual adjustments not available, use empty dict
        contextual_dict = {}

    # Prepare output
    columns = [
        "game_id",
        "visiting_team",
        "visiting_team_elo_rating",
        "home_team",
        "home_team_elo_rating",
        "winning_team",
        "elo_change",
        "margin",
        "contextual_adjustment",
        "ingested_at"
    ]
    rows = []

    from datetime import datetime
    ingested_at = datetime.now()

    # Process each game and update ELO ratings
    for (game_id, vteam, hteam, winner, game_result, neutral_site, margin) in nfl_elo_latest.fetchall():
        # Get current ELO ratings
        helo = working_elo.get(hteam)
        velo = working_elo.get(vteam)

        if helo is None or velo is None:
            raise ValueError(f"Missing ELO rating for team: {hteam if helo is None else vteam}")

        # Get contextual adjustment for this game (default to 0 if not found)
        contextual_adj = contextual_dict.get(game_id, 0.0)

        # Calculate ELO change with MOV multiplier and contextual adjustments
        elo_change = calc_elo_diff(
            game_result=game_result,
            home_elo=helo,
            visiting_elo=velo,
            home_adv=0 if neutral_site == 1 else home_adv,
            scoring_margin=margin,
            contextual_adjustment=contextual_adj,
            k_factor=k_factor,
            elo_scale=elo_scale,
            mov_multiplier_base=mov_multiplier_base,
            mov_multiplier_divisor=mov_multiplier_divisor
        )

        # Store pre-game ratings, ELO change, and contextual adjustment
        rows.append((game_id, vteam, velo, hteam, helo, winner, elo_change, margin, contextual_adj, ingested_at))

        # Update working ELO ratings for next game
        # elo_change is from home team's perspective (negative = home gains)
        working_elo[hteam] -= elo_change
        working_elo[vteam] += elo_change

    return pd.DataFrame(columns=columns, data=rows)