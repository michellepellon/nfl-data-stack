# Phase 2: Statistical Rigor

**Status**: In Progress
**Started**: 2025-11-08
**Goal**: Add robust statistical validation and uncertainty quantification to Monte Carlo predictions

## Overview

Phase 1 established a working Monte Carlo simulation with 10,000 scenarios per game. Phase 2 focuses on adding statistical rigor to ensure predictions are:
- Properly calibrated
- Include quantified uncertainty
- Validated against historical performance
- Tested for distributional properties

## Objectives

1. **Bootstrap Confidence Intervals**: Add 95% CIs for all playoff probability metrics
2. **Calibration Validation**: Verify ELO predictions match actual outcomes
3. **Temporal Cross-Validation**: Test prediction accuracy across historical seasons
4. **Distributional Tests**: Validate statistical properties of simulation outputs
5. **Documentation**: Comprehensive statistical methodology documentation

## Implementation Tasks

### 1. Bootstrap Confidence Intervals (Priority 1)

**Goal**: Provide uncertainty bounds for playoff probabilities

**Current State**:
- `nfl_reg_season_summary.sql` already calculates 5th/95th percentiles for wins and seeds
- These are percentiles from Monte Carlo scenarios, not bootstrap CIs

**Implementation**:
- Create `nfl_playoff_probabilities_with_ci.sql` model
- Calculate playoff probability point estimates from Monte Carlo results
- Implement bootstrap resampling (1000+ bootstrap samples)
- Calculate 95% confidence intervals using percentile method
- Add confidence interval width as uncertainty metric

**Metrics to Add CIs**:
- Playoff probability
- First-round bye probability
- Division win probability
- Conference championship probability
- Super Bowl probability

**Output Format**:
```
Team: Kansas City Chiefs
Playoff Probability: 95.3% [92.1% - 97.8%]
First Round Bye: 68.5% [63.2% - 73.9%]
```

### 2. Calibration Validation (Priority 2)

**Goal**: Verify ELO predictions are well-calibrated

**Calibration Test**:
- When ELO predicts 70% home win probability, home team should win ~70% of time
- Create calibration bins (0-10%, 10-20%, ..., 90-100%)
- Compare predicted vs actual win rates per bin
- Calculate Brier score for overall accuracy
- Generate calibration plots

**Implementation**:
- Create `nfl_calibration_validation.sql` model
- Group historical predictions by probability bins
- Calculate actual win percentage per bin
- Compute Brier score: `avg((predicted - actual)^2)`
- Add calibration tests to dbt tests

**Success Criteria**:
- Brier score < 0.25 (lower is better, random = 0.25)
- Calibration curve closely follows y=x diagonal
- No systematic over/under-prediction

### 3. Temporal Cross-Validation (Priority 3)

**Goal**: Validate prediction accuracy across multiple seasons

**Methodology**:
- Use walk-forward validation (2020 → 2021 → 2022 → 2023 → 2024)
- Train ELO on seasons 1-N, predict season N+1
- Measure prediction accuracy for each season
- Track ELO rating drift over time

**Metrics**:
- Prediction accuracy (% correct picks)
- Log loss
- Mean absolute error on win probabilities
- Playoff bracket prediction accuracy

**Implementation**:
- Create `nfl_temporal_validation.sql` model
- Split data by season
- Calculate rolling accuracy metrics
- Test for concept drift in ELO ratings

### 4. Distributional Tests (Priority 4)

**Goal**: Validate statistical properties using dbt-expectations

**Install dbt-expectations**:
```yaml
# transform/packages.yml
packages:
  - package: calogica/dbt-expectations
    version: 0.10.4
```

**Tests to Add**:

**A. Win Distribution Tests**:
- `expect_column_values_to_be_between` (wins: 0-17)
- `expect_column_mean_to_be_between` (expected wins per team)
- `expect_column_stdev_to_be_between` (variance validation)

**B. Probability Tests**:
- `expect_column_values_to_be_between` (probabilities: 0-1)
- `expect_column_sum_to_equal` (complementary probabilities sum to 1)
- `expect_column_values_to_be_increasing` (ranked probabilities)

**C. Simulation Quality Tests**:
- `expect_column_distinct_count_to_equal` (10,000 scenarios)
- `expect_compound_columns_to_be_unique` (game_id + scenario_id)
- `expect_table_row_count_to_equal_other_table` (consistency checks)

**D. ELO Rating Tests**:
- `expect_column_values_to_be_between` (ELO: 1000-2000)
- `expect_column_mean_to_be_between` (ELO mean ~1500)
- `expect_column_to_exist` (required fields)

**Implementation**:
- Add dbt-expectations to packages.yml
- Create schema.yml files with expectation tests
- Run `dbt test` to validate all assumptions
- Document test failures and remediation

### 5. Statistical Documentation (Priority 5)

**Documents to Create**:

**A. `docs/statistical_methodology.md`**:
- ELO rating calculation methodology
- Monte Carlo simulation approach
- Bootstrap resampling procedure
- Calibration validation methods
- Assumptions and limitations

**B. `docs/interpretation_guide.md`**:
- How to read confidence intervals
- What playoff probabilities mean
- When to trust vs question predictions
- Known edge cases and limitations

**C. `docs/validation_results.md`**:
- Calibration test results
- Cross-validation accuracy
- Distributional test results
- Comparison to Vegas lines

## Success Metrics

Phase 2 is complete when:

- ✅ All playoff probabilities include 95% confidence intervals
- ✅ Brier score < 0.25 on historical predictions
- ✅ Calibration curve shows R² > 0.95
- ✅ All dbt-expectations tests passing
- ✅ Statistical methodology fully documented
- ✅ Rill dashboards updated with confidence intervals
- ✅ Validation results documented

## Technical Approach

### Bootstrap Resampling Algorithm

```sql
-- Pseudo-code for bootstrap CI calculation
WITH bootstrap_samples AS (
  SELECT
    team,
    -- Resample with replacement from 10,000 scenarios
    sample_with_replacement(scenario_id, 10000) as bootstrap_sample
  FROM nfl_reg_season_end
  CROSS JOIN generate_series(1, 1000) as bootstrap_iteration
),
bootstrap_stats AS (
  SELECT
    team,
    bootstrap_iteration,
    AVG(made_playoffs) as playoff_prob
  FROM bootstrap_samples
  GROUP BY team, bootstrap_iteration
)
SELECT
  team,
  PERCENTILE_CONT(0.025) WITHIN GROUP (ORDER BY playoff_prob) as ci_lower,
  AVG(playoff_prob) as point_estimate,
  PERCENTILE_CONT(0.975) WITHIN GROUP (ORDER BY playoff_prob) as ci_upper
FROM bootstrap_stats
GROUP BY team
```

### Calibration Calculation

```sql
WITH calibration_bins AS (
  SELECT
    FLOOR(home_team_win_probability / 10) * 10 as bin_lower,
    AVG(home_team_win_probability / 100) as avg_predicted,
    AVG(CASE WHEN winner = home_team THEN 1.0 ELSE 0.0 END) as avg_actual,
    COUNT(*) as n_games
  FROM historical_games
  GROUP BY bin_lower
)
SELECT
  bin_lower || '-' || (bin_lower + 10) || '%' as probability_bin,
  avg_predicted,
  avg_actual,
  ABS(avg_predicted - avg_actual) as calibration_error,
  n_games
FROM calibration_bins
ORDER BY bin_lower
```

## Dependencies

- dbt-expectations package
- Historical game results with actual outcomes
- Sufficient data for temporal validation (3+ seasons)

## Risks and Mitigations

**Risk**: Bootstrap sampling may be slow on large datasets
**Mitigation**: Use DuckDB's efficient sampling, parallelize where possible

**Risk**: Calibration may show poor results for low-sample bins
**Mitigation**: Combine bins with < 100 games, use Bayesian smoothing

**Risk**: Temporal validation requires historical ELO ratings
**Mitigation**: Retroactively calculate historical ELO or use nflfastR data

## Timeline

- Week 1: Bootstrap CIs + Rill dashboard updates
- Week 2: Calibration validation + Brier scores
- Week 3: Temporal cross-validation framework
- Week 4: dbt-expectations tests + documentation

## Next Steps

1. Start with bootstrap CI implementation
2. Update Rill dashboards to display confidence intervals
3. Validate against known results (e.g., Chiefs should have high playoff probability with narrow CI)
4. Move to calibration validation once CIs are stable
