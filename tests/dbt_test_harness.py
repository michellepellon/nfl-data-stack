"""
DBT Test Harness for Python Models

Provides a mock dbt context for testing dbt Python models that use ref()
to reference other models. This allows testing complex models like
nfl_tiebreakers_optimized.py with synthetic data.

Usage:
    from tests.dbt_test_harness import DbtTestHarness

    # Create test data
    simulator_df = pl.DataFrame({...})
    ratings_df = pl.DataFrame({...})

    # Build harness
    harness = DbtTestHarness()
    harness.add_ref("nfl_reg_season_simulator", simulator_df)
    harness.add_ref("nfl_ratings", ratings_df)

    # Call model
    result = model(harness.dbt, harness.session)
"""

import pandas as pd
import polars as pl
from typing import Dict, Union


class MockDbtRef:
    """Mock ref object that wraps a DataFrame"""

    def __init__(self, df: Union[pd.DataFrame, pl.DataFrame]):
        if isinstance(df, pl.DataFrame):
            self._df = df.to_pandas()
        else:
            self._df = df

    def df(self) -> pd.DataFrame:
        """Return the DataFrame (matches dbt behavior)"""
        return self._df


class MockDbtContext:
    """Mock dbt context with ref() support"""

    def __init__(self, refs: Dict[str, Union[pd.DataFrame, pl.DataFrame]]):
        self._refs = {name: MockDbtRef(df) for name, df in refs.items()}

    def ref(self, model_name: str) -> MockDbtRef:
        """Mock ref() function that returns registered DataFrames"""
        if model_name not in self._refs:
            raise ValueError(
                f"Model '{model_name}' not registered in test harness. "
                f"Available models: {list(self._refs.keys())}"
            )
        return self._refs[model_name]

    def config(self, **kwargs):
        """Mock config() function (no-op for tests)"""
        pass


class DbtTestHarness:
    """
    Test harness for dbt Python models

    Provides a mock dbt context that can be passed to model() functions
    for testing without requiring actual dbt infrastructure.
    """

    def __init__(self):
        self._refs: Dict[str, Union[pd.DataFrame, pl.DataFrame]] = {}
        self._dbt_context = None

    def add_ref(self, model_name: str, df: Union[pd.DataFrame, pl.DataFrame]) -> None:
        """
        Register a DataFrame to be returned by dbt.ref(model_name)

        Args:
            model_name: Name of the model (e.g., "nfl_ratings")
            df: DataFrame to return when ref(model_name) is called
        """
        self._refs[model_name] = df
        # Reset context so it gets rebuilt with new refs
        self._dbt_context = None

    @property
    def dbt(self) -> MockDbtContext:
        """Get the mock dbt context"""
        if self._dbt_context is None:
            self._dbt_context = MockDbtContext(self._refs)
        return self._dbt_context

    @property
    def session(self):
        """Mock session object (not used by most models)"""
        return None

    def reset(self) -> None:
        """Clear all registered refs"""
        self._refs = {}
        self._dbt_context = None
