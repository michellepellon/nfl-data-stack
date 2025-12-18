"""
ELO Calibrated Predictions

Applies isotonic regression calibration to raw ELO win probabilities to produce
better-calibrated predictions that match actual outcomes.

This model:
1. Loads raw ELO probabilities from rollforward
2. Applies saved isotonic regression model (prefers temporal version)
3. Outputs calibrated probabilities for each game

Calibration model priority:
1. models/elo_calibration_temporal.pkl (walk-forward validated)
2. models/elo_calibration.pkl (original, trained on all data)
3. No calibration (raw probabilities passed through)
"""

import pandas as pd
import pickle
from pathlib import Path


def load_calibration_model(project_root: Path):
    """
    Load calibration model with fallback chain.

    Priority:
    1. elo_calibration_temporal.pkl (walk-forward validated)
    2. elo_calibration.pkl (original)
    3. None (use raw probabilities)

    Returns tuple of (model, model_type) where model_type is
    'temporal', 'original', or 'none'
    """
    temporal_path = project_root / "models" / "elo_calibration_temporal.pkl"
    original_path = project_root / "models" / "elo_calibration.pkl"

    if temporal_path.exists():
        with open(temporal_path, 'rb') as f:
            return pickle.load(f), 'temporal'
    elif original_path.exists():
        with open(original_path, 'rb') as f:
            return pickle.load(f), 'original'
    else:
        return None, 'none'


def model(dbt, sess):
    """
    dbt Python model to apply calibration to ELO predictions

    Returns a DataFrame with calibrated win probabilities
    """
    # Load the fitted isotonic regression model
    # Use absolute path since __file__ is not reliable in dbt execution
    import os
    project_root = Path(os.getcwd()).parent

    iso_reg, model_type = load_calibration_model(project_root)

    if model_type == 'none':
        print("WARNING: No calibration model found. Using raw probabilities.")
        print("Run 'python scripts/fit_calibration_temporal.py' to create one.")

    # Get configuration
    home_adv = dbt.config.get("nfl_elo_offset", 52.0)
    mid_shrinkage = dbt.config.get("mid_confidence_shrinkage", 0.15)

    # Load ELO rollforward data
    rollforward = dbt.ref("nfl_elo_rollforward").df()

    # Calculate raw ELO probabilities
    rollforward['raw_home_win_prob'] = 1.0 / (
        1.0 + 10.0 ** (
            -(rollforward['home_team_elo_rating'] - rollforward['visiting_team_elo_rating'] + home_adv) / 400.0
        )
    )

    # Apply calibration (or pass through raw if no model)
    if iso_reg is not None:
        rollforward['calibrated_home_win_prob'] = iso_reg.predict(
            rollforward['raw_home_win_prob'].values
        )
    else:
        # No calibration model available - use raw probabilities
        rollforward['calibrated_home_win_prob'] = rollforward['raw_home_win_prob']

    # Apply mid-confidence shrinkage to reduce overconfidence in 55-70% range
    # Shrinks predictions toward 50% for mid-range probabilities
    def apply_shrinkage(prob, shrinkage_factor=0.15, lower=0.55, upper=0.70):
        """Shrink probabilities in mid-confidence range toward 50%"""
        if lower <= prob <= upper:
            # Linear shrinkage toward 0.5
            return prob - shrinkage_factor * (prob - 0.5)
        elif (1 - upper) <= prob <= (1 - lower):
            # Mirror for low probabilities (30-45%)
            return prob - shrinkage_factor * (prob - 0.5)
        return prob

    rollforward['calibrated_home_win_prob'] = rollforward['calibrated_home_win_prob'].apply(
        lambda x: apply_shrinkage(x, mid_shrinkage)
    )

    rollforward['calibrated_away_win_prob'] = 1.0 - rollforward['calibrated_home_win_prob']

    # Track which calibration model was used
    rollforward['calibration_model_type'] = model_type

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
        'calibration_model_type',
        'winning_team',
        'elo_change',
        'margin'
    ]

    from datetime import datetime
    result = rollforward[output_columns].copy()
    result['ingested_at'] = datetime.now()

    return result
