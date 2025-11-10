"""
Shared pytest fixtures for NFL Data Stack tests

Provides reusable test data, database connections, and utility functions
for unit, integration, and end-to-end tests.
"""

import pytest
import pandas as pd
from pathlib import Path


@pytest.fixture
def sample_elo_ratings():
    """Sample ELO ratings for test teams"""
    return {
        "Kansas City Chiefs": 1650.0,
        "Buffalo Bills": 1600.0,
        "Cleveland Browns": 1450.0,
        "New England Patriots": 1500.0,
        "Detroit Lions": 1550.0,
    }


@pytest.fixture
def even_matchup():
    """Test case: evenly matched teams (both 1500 ELO)"""
    return {
        "home_elo": 1500.0,
        "visiting_elo": 1500.0,
        "home_adv": 52.0,
        "game_result": 0,  # home team wins
        "scoring_margin": 7.0,
        "k_factor": 20.0,
    }


@pytest.fixture
def blowout_game():
    """Test case: blowout win (24+ point margin)"""
    return {
        "home_elo": 1600.0,
        "visiting_elo": 1450.0,
        "home_adv": 52.0,
        "game_result": 0,  # home team wins by blowout
        "scoring_margin": 28.0,
        "k_factor": 20.0,
    }


@pytest.fixture
def upset_game():
    """Test case: underdog wins"""
    return {
        "home_elo": 1650.0,  # strong home team
        "visiting_elo": 1450.0,  # weak visiting team
        "home_adv": 52.0,
        "game_result": 1,  # visiting team wins (upset!)
        "scoring_margin": 10.0,
        "k_factor": 20.0,
    }


@pytest.fixture
def tie_game():
    """Test case: tie game"""
    return {
        "home_elo": 1500.0,
        "visiting_elo": 1500.0,
        "home_adv": 52.0,
        "game_result": 0.5,  # tie
        "scoring_margin": 0.0,
        "k_factor": 20.0,
    }


@pytest.fixture
def neutral_site_game():
    """Test case: neutral site game (no home advantage)"""
    return {
        "home_elo": 1550.0,
        "visiting_elo": 1550.0,
        "home_adv": 0.0,  # neutral site
        "game_result": 0,
        "scoring_margin": 3.0,
        "k_factor": 20.0,
    }


@pytest.fixture
def project_root():
    """Path to project root directory"""
    return Path(__file__).parent.parent


@pytest.fixture
def data_catalog_dir(project_root):
    """Path to data catalog directory (Parquet files)"""
    return project_root / "data" / "data_catalog"


@pytest.fixture
def transform_dir(project_root):
    """Path to transform directory (dbt models)"""
    return project_root / "transform"


@pytest.fixture
def sample_game_results():
    """Sample game results for testing ELO rollforward"""
    return pd.DataFrame(
        [
            {
                "game_id": 1,
                "visiting_team": "Buffalo Bills",
                "home_team": "Kansas City Chiefs",
                "winning_team": "Kansas City Chiefs",
                "game_result": 0,  # home win
                "neutral_site": 0,
                "margin": 3,
            },
            {
                "game_id": 2,
                "visiting_team": "Cleveland Browns",
                "home_team": "Buffalo Bills",
                "winning_team": "Buffalo Bills",
                "game_result": 0,  # home win
                "neutral_site": 0,
                "margin": 14,
            },
            {
                "game_id": 3,
                "visiting_team": "Kansas City Chiefs",
                "home_team": "Cleveland Browns",
                "winning_team": "Kansas City Chiefs",
                "game_result": 1,  # visiting win (upset)
                "neutral_site": 0,
                "margin": 7,
            },
        ]
    )


@pytest.fixture
def elo_config():
    """Standard ELO configuration parameters"""
    return {
        "nfl_elo_offset": 52.0,
        "elo_k_factor": 20.0,
        "scenarios": 10000,
        "random_seed": 42,
    }
