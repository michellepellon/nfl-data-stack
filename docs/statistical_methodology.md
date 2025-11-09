# Statistical Methodology

**Last Updated**: 2025-11-08
**Version**: 1.0

## Overview

This document describes the statistical methods used in the NFL Monte Carlo simulation project to generate playoff predictions with quantified uncertainty.

## Table of Contents

1. [ELO Rating System](#1-elo-rating-system)
2. [Monte Carlo Simulation](#2-monte-carlo-simulation)
3. [Confidence Intervals](#3-confidence-intervals)
4. [Validation Methods](#4-validation-methods)
5. [Assumptions and Limitations](#5-assumptions-and-limitations)
6. [Interpreting Results](#6-interpreting-results)

## 1. ELO Rating System

### Overview

We use the ELO rating system to quantify team strength and predict game outcomes. ELO ratings are dynamic, updating after each game based on actual results.

### Initial Ratings

Teams start with ELO ratings provided by historical data sources. The ratings are centered around 1500 with a standard deviation that reflects competitive balance in the NFL.

### Home Field Advantage

We apply a home field adjustment of **52 ELO points** (configurable via `nfl_elo_offset` variable) to the home team's rating before calculating win probability. This represents approximately a 7.5% boost to the home team's win probability for evenly matched teams.

### Win Probability Calculation

For a given matchup, the win probability is calculated using the logistic function:

```
win_prob_home = 1 / (1 + 10^(-(elo_home + 52 - elo_away) / 400))
```

This formula is standard in ELO systems and ensures:
- Win probabilities are bounded between 0 and 1
- A 400-point ELO difference equals ~90% win probability
- The relationship is smooth and monotonic

### ELO Updates (IMPLEMENTED)

**Status**: ✅ Fully implemented with margin-of-victory multiplier

After each game, team ratings are updated using:

```
elo_new = elo_old + K * MOV_multiplier * (actual_result - expected_result)
```

Where:
- `K = 20` (configurable via `elo_k_factor` variable)
- `MOV_multiplier = ln(|point_diff| + 1) * (2.2 / (|elo_diff| * 0.001 + 2.2))`
- `actual_result = 1` for win, `0` for loss, `0.5` for tie
- `expected_result = win_probability`
- `elo_diff = winner_elo - loser_elo` (accounts for upset magnitude)

**Implementation Details**:
- Ratings are updated in chronological order (by game_id)
- Each team's rating rolls forward game-by-game
- Home field advantage (52 points) is factored into expected win probability
- Neutral site games have no home advantage
- The MOV multiplier increases rating changes for:
  - Blowouts (larger point differentials)
  - Upsets (underdog wins)

## 2. Monte Carlo Simulation

### Simulation Framework

We use Monte Carlo simulation to account for the inherent randomness in game outcomes. Even with accurate win probabilities, the actual results are stochastic.

### Scenario Generation

**Number of Scenarios**: 10,000 per simulation run (configurable via `scenarios` variable)

**Random Seed**: All simulations use `random_seed = 42` for reproducibility

### Simulation Process

For each of the 10,000 scenarios:

1. **Initialize**: Start with current league standings
2. **Iterate through remaining games**: For each game:
   - Calculate home team win probability using ELO ratings
   - Generate random number between 0 and 1
   - If random number < win probability, home team wins; otherwise away team wins
   - Update standings with the simulated result
3. **Apply Tiebreakers**: After all games simulated, apply NFL tiebreaking rules to determine playoff seeding
4. **Record Results**: Store playoff outcomes (made playoffs, first round bye, seed, wins, etc.)

### Tiebreaking Rules

We implement comprehensive NFL tiebreaking rules (see `nfl_tiebreakers_optimized.sql`):

1. Head-to-head record (if applicable)
2. Division record
3. Common games record
4. Conference record
5. Strength of victory
6. Strength of schedule
7. (Additional tiebreakers as needed)

### Aggregation

After 10,000 scenarios, we calculate:
- **Playoff Probability**: Proportion of scenarios where team makes playoffs
- **Bye Probability**: Proportion of scenarios where team gets first-round bye
- **Average Wins**: Mean wins across all scenarios
- **Average Seed**: Mean playoff seed across all scenarios

## 3. Confidence Intervals

### Why Confidence Intervals?

Monte Carlo point estimates (e.g., "75% playoff probability") don't convey the uncertainty in those estimates. Confidence intervals provide bounds that quantify this uncertainty.

### Wilson Score Interval (Binary Outcomes)

For binary outcomes like "made playoffs" or "got first-round bye", we use the **Wilson score interval**, which is more accurate than the normal approximation, especially for proportions near 0 or 1.

**Formula**:

For a proportion `p` observed in `n` scenarios, the 95% confidence interval is:

```
CI = (p + z²/2n ± z√(p(1-p)/n + z²/4n²)) / (1 + z²/n)
```

Where:
- `z = 1.96` (for 95% confidence level)
- `n = 10,000` (number of Monte Carlo scenarios)

**Properties**:
- Accounts for finite sample size
- More conservative (wider intervals) for extreme probabilities
- Asymmetric around the point estimate for proportions near 0 or 1

### Empirical Percentile Intervals (Continuous Outcomes)

For continuous outcomes like "wins" or "seed", we use empirical percentiles from the Monte Carlo distribution:

**Formula**:

```
95% CI = [2.5th percentile, 97.5th percentile]
```

This directly leverages the Monte Carlo samples to create a non-parametric confidence interval.

### Interpretation

**Example**: "Kansas City Chiefs: 72.9% [72.0% - 73.7%]"

This means:
- **Point Estimate**: 72.9% of the 10,000 scenarios had the Chiefs making the playoffs
- **Confidence Interval**: We are 95% confident the "true" playoff probability (if we could run infinite scenarios) lies between 72.0% and 73.7%
- **Narrow CI**: High certainty in the estimate (large sample size + moderate probability)

**Example**: "Cleveland Browns: 0.5% [0.4% - 0.7%]"

- **Point Estimate**: Only 0.5% of scenarios had the Browns making playoffs (50 out of 10,000)
- **Confidence Interval**: True probability likely between 0.4% and 0.7%
- **Wider Relative CI**: Despite narrow absolute range, the CI is ~75% of the point estimate, showing higher relative uncertainty for rare events

## 4. Validation Methods

### Calibration Analysis (Future)

**Goal**: Verify that predicted probabilities match actual frequencies

**Method**:
- Bin predictions (0-10%, 10-20%, ..., 90-100%)
- Compare predicted vs actual win rates per bin
- Calculate Brier score: `avg((predicted - actual)²)`
- Generate calibration plot

**Success Criteria**:
- Brier score < 0.25 (random baseline)
- Calibration curve closely follows y=x diagonal
- R² > 0.95 for calibration fit

### Temporal Cross-Validation (Future)

**Goal**: Test prediction accuracy across historical seasons

**Method**:
- Walk-forward validation (train on 2020-2023, predict 2024)
- Measure prediction accuracy, log loss, MAE
- Track ELO rating drift over time

## 5. Assumptions and Limitations

### Assumptions

1. **ELO Accuracy**: Team strength is well-captured by ELO ratings
2. **Independence**: Game outcomes are independent (no hot streaks, injuries not modeled)
3. **Stationarity**: Team strength doesn't change mid-season (except via ELO updates)
4. **Home Advantage**: 52 ELO points is constant across all stadiums
5. **Tiebreaker Completeness**: Our tiebreaking logic correctly implements NFL rules

### Limitations

1. **No Injury Modeling**: Player injuries are not considered
2. **No Weather**: Game conditions (weather, travel) not modeled
3. **No Momentum**: Recent performance trends not explicitly modeled
4. **Fixed ELO**: Current implementation doesn't update ELO mid-season
5. **Sample Size**: 10,000 scenarios may underestimate tail probabilities (<0.1%)

### Known Edge Cases

- **Rare Events**: Probabilities below 0.1% have high relative uncertainty
- **Late Season**: Predictions become more certain as fewer games remain
- **Tiebreakers**: Complex 3+ team ties may not be perfectly resolved

## 6. Interpreting Results

### Playoff Probabilities

**High Confidence (>90%)**:
- Team is very likely to make playoffs
- Narrow CI indicates certainty
- Focus on seeding, not playoff qualification

**Medium Confidence (30-70%)**:
- Team is "on the bubble"
- Wins in next 1-2 games significantly impact probability
- Wide CI indicates high variance in outcomes

**Low Confidence (<10%)**:
- Team needs many things to go right
- Often requires winning out + help from other teams
- Wider relative CI due to low sample counts

### Confidence Interval Width

**Narrow CI (< 5% width)**:
- High certainty in the estimate
- Typical for extreme probabilities (>95% or <5%) OR large sample sizes
- Result is robust to additional simulation runs

**Wide CI (> 10% width)**:
- Substantial uncertainty
- May indicate borderline teams with volatile futures
- Consider running more scenarios if critical decision

### Win Projections

**Example**: "Buffalo Bills: 12.3 [10.0 - 15.0]"

- **Point Estimate**: Average 12.3 wins expected
- **Range**: 95% of scenarios had 10-15 wins
- **Volatility**: 5-win range shows moderate variance

**Interpretation**:
- Chiefs likely win division (12+ wins)
- Still possible to finish 10-7 (wild card) or 14-3 (division champ)
- Schedule difficulty and variance in outcomes create this range

## Appendix A: Mathematical Notation

### ELO System

- `E_i` = ELO rating of team i
- `H` = Home field advantage (52 points)
- `P(i wins)` = Win probability for team i
- `K` = ELO K-factor (learning rate)
- `MOV` = Margin of victory

### Confidence Intervals

- `p` = Sample proportion
- `n` = Sample size (10,000)
- `z` = Z-score for desired confidence level (1.96 for 95%)
- `CI` = Confidence interval
- `Q(α)` = α-th quantile of Monte Carlo distribution

### Calibration

- `B` = Brier score
- `N` = Number of predictions
- `f_i` = Predicted probability for game i
- `o_i` = Actual outcome for game i (0 or 1)

```
Brier Score: B = (1/N) Σ(f_i - o_i)²
```

## Appendix B: References

1. FiveThirtyEight NFL ELO Methodology: https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/
2. Wilson Score Interval: Agresti, A. & Coull, B.A. (1998). "Approximate is better than 'exact' for interval estimation of binomial proportions"
3. NFL Tiebreaking Procedures: https://www.nfl.com/standings/tie-breaking-procedures
4. Monte Carlo Methods: Kroese, D.P. et al. (2014). "Why the Monte Carlo method is so important today"
5. Brier Score: Brier, G.W. (1950). "Verification of forecasts expressed in terms of probability"

## Appendix C: Code Examples

### Calculating Wilson CI in SQL

```sql
WITH playoff_stats AS (
  SELECT
    team,
    AVG(made_playoffs::FLOAT) AS p,
    COUNT(*) AS n
  FROM nfl_reg_season_end
  GROUP BY team
)
SELECT
  team,
  p AS point_estimate,
  (p + 1.96*1.96/(2*n) - 1.96*SQRT(p*(1-p)/n + 1.96*1.96/(4*n*n))) / (1 + 1.96*1.96/n) AS ci_lower,
  (p + 1.96*1.96/(2*n) + 1.96*SQRT(p*(1-p)/n + 1.96*1.96/(4*n*n))) / (1 + 1.96*1.96/n) AS ci_upper
FROM playoff_stats
```

### Calculating Empirical Percentiles in SQL

```sql
SELECT
  team,
  PERCENTILE_CONT(0.025) WITHIN GROUP (ORDER BY wins) AS wins_ci_lower,
  PERCENTILE_CONT(0.975) WITHIN GROUP (ORDER BY wins) AS wins_ci_upper
FROM nfl_reg_season_end
GROUP BY team
```

---

**Prepared by**: Claude Code
**Review Status**: Initial Draft
**Next Review**: After implementing calibration validation
