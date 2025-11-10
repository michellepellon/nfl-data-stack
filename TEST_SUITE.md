# NFL Data Stack Test Suite

Comprehensive test coverage for ELO calculations, Monte Carlo simulation, tiebreaker logic, and data quality validation.

## Quick Start

```bash
# Run all tests
just test-all

# Run unit tests only (fast)
just test-unit

# Run integration tests only
just test-integration

# Run with coverage report
just test-coverage
```

## Test Structure

```
tests/
├── unit/                      # Unit tests for pure functions
│   └── test_elo_calculations.py  # 20 tests for calc_elo_diff()
├── integration/               # Integration tests for models and data
│   ├── test_tiebreakers.py       # 25 tests for playoff seeding logic
│   └── test_data_validation.py   # 12 tests for Parquet data quality
└── e2e/                       # End-to-end tests (future)
```

## Test Categories

### Unit Tests (20 tests, 100% passing)
**File**: `tests/unit/test_elo_calculations.py`

Tests the core ELO calculation function (`calc_elo_diff`) with comprehensive coverage:

- **Basic scenarios**: Even matchup, blowout, upset, tie
- **Edge cases**: Minimum margin, zero margin, neutral site, large ELO differences
- **Formula validation**: Win probability calculation, MOV multiplier behavior
- **Invariants**: Finite results, symmetry, K-factor scaling, bounded changes
- **Regression**: Known game calculations

**Coverage**: 100% of `calc_elo_diff()` function

**Run**: `just test-unit`

### Integration Tests - Tiebreakers (25 tests, 3 passing, 22 skipped)
**File**: `tests/integration/test_tiebreakers.py`

Tests NFL playoff tiebreaker logic:

**Passing tests (3)**:
- `test_build_long_games` - Converts game results to team perspective
- `test_team_records` - Calculates win-loss records
- `test_h2h_summary` - Computes head-to-head records

**Skipped tests (22)** - Require full dbt model integration:
- Division winner determination
- Wild card seeding
- Specific tiebreaker rules (wins, h2h, conference, common games, SoV, SoS)
- Three-way tie scenarios
- Historical playoff validation (2020-2024)
- Invariant checks (7 teams per conference, unique ranks, etc.)

**Run**: `pytest tests/integration/test_tiebreakers.py -v`

### Integration Tests - Data Validation (12 tests, 9 passing, 2 skipped, 1 xfail)
**File**: `tests/integration/test_data_validation.py`

Validates Parquet file schemas and data quality:

**Schema validation (3 passing)**:
- `test_ratings_parquet_schema`
- `test_simulator_parquet_schema`
- `test_playoff_probabilities_schema`

**Data quality rules (6 passing, 1 xfail)**:
- `test_elo_ratings_in_valid_range` - ELO between 1000-2000
- `test_win_probabilities_sum_to_100` - Probabilities sum correctly
- `test_confidence_intervals_valid` - CI lower < point < upper
- `test_all_teams_present` - **XFAIL**: Found 33 teams (Washington duplicate)
- `test_week_numbers_valid` - Weeks 1-18 only
- `test_no_null_critical_fields` - No nulls in critical columns

**Data freshness (1 passing)**:
- `test_ratings_freshness` - Updated within 7 days

**ELO rollforward (2 skipped)** - Requires nfl_elo_rollforward.parquet:
- `test_elo_rollforward_has_all_games`
- `test_elo_changes_reasonable`

**Run**: `pytest tests/integration/test_data_validation.py -v`

## Test Markers

Tests are organized with pytest markers for selective execution:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only slow tests
pytest -m slow

# Skip slow tests
pytest -m "not slow"
```

**Available markers**:
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Tests that take significant time

## Coverage Report

After running tests with coverage:

```bash
just test-coverage
```

View HTML coverage report:

```bash
open htmlcov/index.html
```

**Current coverage**:
- `nfl_elo_rollforward.py`: 43% (model() function not tested, calc_elo_diff() is 100%)
- `nfl_tiebreakers_optimized.py`: 20% (helper functions tested, main model() not tested)
- Overall: 2% (many scripts not yet tested)

## Known Issues

### Data Quality Issues Found by Tests

1. **Washington Team Duplicate** (test_all_teams_present xfail)
   - Found both "Washington Commanders" and "Washington Football Team"
   - Legacy data from team rebranding
   - **Action**: Clean up seed data to use only current team name

2. **Deprecated Polars API** (warning in test_team_records)
   - `pl.count()` is deprecated, should use `pl.len()`
   - **File**: `transform/models/nfl/analysis/nfl_tiebreakers_optimized.py:27`
   - **Action**: Update to `pl.len()`

## Future Work

### High Priority
1. **Full dbt model integration tests**
   - Mock dbt context for tiebreaker tests
   - Run full model() functions in test environment
   - Validate against historical NFL playoff results (2020-2024)

2. **Historical regression tests**
   - Download 2020-2024 playoff results
   - Validate tiebreaker logic produces correct seeds
   - Compare ELO calculations to FiveThirtyEight published ratings

3. **End-to-end pipeline tests**
   - Test full dbt run from raw data to predictions
   - Validate JSON output for static site
   - Check data freshness and completeness

### Medium Priority
4. **Script testing**
   - Unit tests for data collection scripts
   - Integration tests for webpage generation
   - Validation of hourly update pipeline

5. **Performance tests**
   - Benchmark Monte Carlo simulation (10k scenarios)
   - Track dbt run time regression
   - Memory usage profiling

### Low Priority
6. **Property-based testing**
   - Use Hypothesis for ELO calculation edge cases
   - Generate random game scenarios
   - Fuzz test tiebreaker logic

## Contributing

When adding new tests:

1. **Follow naming convention**: `test_<what_is_being_tested>.py`
2. **Use descriptive test names**: `test_even_matchup_home_win` not `test_case_1`
3. **Add docstrings**: Explain what the test validates and why
4. **Use fixtures**: Share test data via conftest.py
5. **Mark appropriately**: `@pytest.mark.unit`, `@pytest.mark.integration`, etc.
6. **Update this document**: Add new test categories and known issues

## Troubleshooting

### Tests failing with "File not found"
- Integration tests require Parquet files in `data/data_catalog/`
- Run `just build` to generate missing files

### Import errors
- Ensure pytest is installed: `uv sync`
- Check that `tests/` has `__init__.py` files

### Coverage not working
- Install pytest-cov: `uv add pytest-cov` (already in pyproject.toml)
- Check coverage config in `pyproject.toml`

### Tests too slow
- Run unit tests only: `just test-unit`
- Skip slow tests: `pytest -m "not slow"`
- Use parallel execution: `pytest -n auto` (requires pytest-xdist)

## References

- [pytest documentation](https://docs.pytest.org/)
- [NFL Tiebreaking Procedures](https://www.nfl.com/standings/tie-breaking-procedures)
- [FiveThirtyEight ELO Methodology](https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/)
