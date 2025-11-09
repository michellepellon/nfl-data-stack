"""
ELO Calibrated Predictions

Applies isotonic regression calibration to raw ELO win probabilities to produce
better-calibrated predictions that match actual outcomes.

This model:
1. Loads raw ELO probabilities from rollforward
2. Applies saved isotonic regression model
3. Outputs calibrated probabilities for each game

The calibration model must be fitted first using scripts/fit_calibration.py
"""

import pandas as pd
import pickle
from pathlib import Path


def model(dbt, sess):
    """
    dbt Python model to apply calibration to ELO predictions

    Returns a DataFrame with calibrated win probabilities
    """
    # Load the fitted isotonic regression model
    # Use absolute path since __file__ is not reliable in dbt execution
    import os
    project_root = Path(os.getcwd()).parent
    model_path = project_root / "models" / "elo_calibration.pkl"

    if not model_path.exists():
        raise FileNotFoundError(
            f"Calibration model not found at {model_path}. "
            "Run 'python scripts/fit_calibration.py' first to fit the model."
        )

    with open(model_path, 'rb') as f:
        iso_reg = pickle.load(f)

    # Get configuration
    home_adv = dbt.config.get("nfl_elo_offset", 52.0)

    # Load ELO rollforward data
    rollforward = dbt.ref("nfl_elo_rollforward").df()

    # Calculate raw ELO probabilities
    rollforward['raw_home_win_prob'] = 1.0 / (
        1.0 + 10.0 ** (
            -(rollforward['home_team_elo_rating'] - rollforward['visiting_team_elo_rating'] + home_adv) / 400.0
        )
    )

    # Apply calibration
    rollforward['calibrated_home_win_prob'] = iso_reg.predict(rollforward['raw_home_win_prob'].values)
    rollforward['calibrated_away_win_prob'] = 1.0 - rollforward['calibrated_home_win_prob']

    # Select output columns
    output_columns = [
        'game_id',
        'home_team',
        'visiting_team',
        'home_team_elo_rating',
        'visiting_team_elo_rating',
        'raw_home_win_prob',
        'calibrated_home_win_prob',
        'calibrated_away_win_prob',
        'winning_team',
        'elo_change',
        'margin'
    ]

    from datetime import datetime
    result = rollforward[output_columns].copy()
    result['ingested_at'] = datetime.now()

    return result
