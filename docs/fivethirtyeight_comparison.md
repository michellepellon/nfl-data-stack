# FiveThirtyEight vs nfl-data-stack: Methodology Comparison

**Date**: 2025-11-10
**Status**: Analysis Complete
**Author**: Claude Code

## Executive Summary

The nfl-data-stack implements a **simplified version** of FiveThirtyEight's NFL prediction methodology. The core ELO system is nearly identical, but nfl-data-stack omits several advanced features:

- ❌ No quarterback adjustments (VALUE system)
- ❌ No preseason mean reversion or Vegas total integration
- ❌ No special game context adjustments (bye weeks, playoffs, travel)
- ❌ "Cold" simulations (fixed ratings) vs FiveThirtyEight's "hot" simulations (dynamic ratings)
- ⚠️ Different home field advantage (52 vs 48 points)

**Impact**: The simplified approach is more transparent and easier to validate, but may be less accurate than FiveThirtyEight's production model, especially for:
- Teams with elite/poor QB play
- Teams coming off bye weeks
- Playoff game predictions
- Late-season games where playoff seeding is locked

---

## Detailed Comparison

### 1. ELO Rating System

| Component | FiveThirtyEight | nfl-data-stack | Status |
|-----------|----------------|----------------|--------|
| **K-Factor** | 20 | 20 | ✅ Identical |
| **ELO Scale** | 400 | 400 | ✅ Identical |
| **Mean Rating** | 1505 | 1500 | ⚠️ Minor diff |
| **Home Advantage** | ~48 points (rolling 10-year avg) | 52 points (fixed) | ⚠️ Different |
| **MOV Formula** | `ln(margin+1)` | `ln(margin+1)` | ✅ Identical |
| **MOV Multiplier Base** | Not specified | 2.2 | ⚠️ Unknown if identical |
| **Autocorrelation Adj** | Yes (prevents rating inflation) | ⚠️ Unclear | ⚠️ May be missing |

**Analysis**:

The core ELO formula is nearly identical:

```python
# Both use this formula
elo_change = K * MOV_multiplier * (actual - expected)
```

**Home Field Advantage Difference**:
- **FiveThirtyEight**: ~48 points (rolling 10-year average, updated annually)
- **nfl-data-stack**: 52 points (fixed constant)
- **Impact**: 52 points ≈ 8% home win boost vs 48 points ≈ 7.5% boost
  - For evenly matched teams (1500 vs 1500):
    - FiveThirtyEight: 58.2% home win probability
    - nfl-data-stack: 59.3% home win probability
  - **Difference**: ~1.1 percentage points

**MOV Multiplier**:

FiveThirtyEight describes:
> "natural logarithm of their point differential plus 1 point"

nfl-data-stack implements:
```python
margin_of_victory_multiplier = math.log(abs(scoring_margin) + 1) * (
    mov_multiplier_base / (winner_elo_diff * mov_multiplier_divisor + mov_multiplier_base)
)
```

Where `mov_multiplier_base = 2.2` and `mov_multiplier_divisor = 0.001`

This matches FiveThirtyEight's description, but the exact parameter values (2.2, 0.001) are not publicly documented by FiveThirtyEight.

**Autocorrelation Adjustment**:

FiveThirtyEight mentions:
> "scales down margin credit for favorite teams to prevent rating inflation"

The nfl-data-stack MOV formula includes `winner_elo_diff` in the denominator, which reduces the multiplier when the favorite wins by a large margin (large positive `winner_elo_diff`). This appears to implement the autocorrelation adjustment, though the exact matching to FiveThirtyEight's approach cannot be verified without their source code.

---

### 2. Preseason Ratings & Mean Reversion

| Feature | FiveThirtyEight | nfl-data-stack | Status |
|---------|----------------|----------------|--------|
| **Preseason Formula** | 1/3 previous (regressed 1/3 to 1505) + 2/3 Vegas totals | Manual initial ratings | ❌ Not implemented |
| **Mean Reversion** | 1/3 toward 1505 each offseason | None | ❌ Not implemented |
| **Vegas Integration** | Uses Vegas win totals for preseason calibration | None | ❌ Not implemented |
| **Expansion Teams** | 1300 rating | Not specified | ⚠️ Unknown |

**Analysis**:

FiveThirtyEight's preseason approach:
```
preseason_elo = (1/3) * revert_to_mean(previous_elo, 1505, 1/3) + (2/3) * vegas_to_elo(win_totals)
```

This has two key benefits:
1. **Captures offseason changes**: Vegas totals reflect draft, free agency, coaching changes
2. **Prevents extreme ratings**: Mean reversion keeps ratings from drifting too far

**nfl-data-stack** starts each season with manual initial ratings (from `nfl_raw_team_ratings`), which likely come from external sources or previous season carry-forward.

**Impact**:
- Preseason predictions may be less accurate without Vegas total integration
- Ratings may drift over multiple seasons without mean reversion
- Offseason changes (new QB, coaching change) not automatically reflected

**Recommendation**:
Consider implementing preseason mean reversion:
```python
# After each season
new_elo = old_elo - (1/3) * (old_elo - 1505)
```

And optionally integrating Vegas win totals for teams with major roster changes.

---

### 3. Quarterback Adjustments

| Feature | FiveThirtyEight | nfl-data-stack | Status |
|---------|----------------|----------------|--------|
| **QB VALUE System** | Yes (added 2019) | No | ❌ Not implemented |
| **Individual QB Rating** | Updated every 10 games | N/A | ❌ Not implemented |
| **Team QB Rating** | Updated every 20 games | N/A | ❌ Not implemented |
| **Elo Conversion** | VALUE × 3.3 = Elo points | N/A | ❌ Not implemented |

**FiveThirtyEight's QB VALUE Formula**:

```
VALUE = -2.2 × Pass Attempts
      + 3.7 × Completions
      + (Passing Yards / 5)
      + 11.3 × Passing TDs
      - 14.1 × Interceptions
      - 8 × Times Sacked
      - 1.1 × Rush Attempts
      + 0.6 × Rushing Yards
      + 15.9 × Rushing TDs
```

This VALUE rating is then converted to ELO points:
```
QB_Elo_Adjustment = VALUE × 3.3
```

**Update Rules**:
- Individual QB: `Rating_new = 0.9 × Rating_old + 0.1 × Game_VALUE` (every 10 games)
- Team QB: Rolling average over 20 games

**Impact of Omission**:

QB adjustments can add/subtract **up to ~100 ELO points** for elite/poor QB play.

Example scenarios where this matters:
- **Elite QB injury**: FiveThirtyEight drops team ~80 points; nfl-data-stack unchanged until games are played
- **Rookie QB breakout**: FiveThirtyEight adjusts upward mid-season; nfl-data-stack lags behind
- **QB controversy**: FiveThirtyEight tracks individual QBs; nfl-data-stack sees only team results

**Why nfl-data-stack may have omitted this**:
- Complexity: Requires play-by-play data integration
- Data availability: ESPN API doesn't provide QB-level stats easily
- Simplicity: Pure ELO is easier to understand and validate
- Transparency: Avoids subjective QB evaluation

**Recommendation**:
- **Short-term**: Document this limitation in predictions ("Does not account for QB changes")
- **Medium-term**: Consider adding manual QB adjustments for major injuries (e.g., -50 points for losing starting QB)
- **Long-term**: Integrate ESPN's Total QBR or Pro Football Reference stats to implement VALUE system

---

### 4. Monte Carlo Simulation

| Feature | FiveThirtyEight | nfl-data-stack | Status |
|---------|----------------|----------------|--------|
| **Scenario Count** | "Tens of thousands" | 10,000 | ✅ Similar |
| **Random Seed** | Not specified | 42 (reproducible) | ➕ Better for testing |
| **Simulation Type** | "Hot" (ratings update during sim) | "Cold" (ratings fixed) | ❌ Major difference |
| **Actual Results** | Uses actual results up to current week | Yes (`include_actuals: true`) | ✅ Identical |

**Critical Difference: "Hot" vs "Cold" Simulations**

**FiveThirtyEight** (from their methodology):
> "We simulate the remainder of the season tens of thousands of times using the Monte Carlo method, and these **'hot' simulations allow team ratings to change after each simulated game**, capturing realistic hot/cold streaks."

**nfl-data-stack**:
- Uses fixed ELO ratings for all games in a scenario
- Ratings do NOT update during simulation
- Each scenario simulates game outcomes, but ELO stays constant

**Example to illustrate the difference**:

Week 10: Chiefs (1650 ELO) vs Bills (1620 ELO) - not yet played

**FiveThirtyEight "hot" simulation**:
1. Scenario 1: Chiefs win → Chiefs ELO becomes 1655 for rest of scenario
2. Scenario 2: Bills win → Bills ELO becomes 1640, Chiefs drop to 1640
3. Each scenario's Week 11+ games use the updated ratings from Week 10 result

**nfl-data-stack "cold" simulation**:
1. Scenario 1: Chiefs win → Chiefs still use 1650 ELO for Week 11+ games
2. Scenario 2: Bills win → Chiefs still use 1650 ELO for Week 11+ games
3. All scenarios use the same fixed ratings regardless of simulated outcomes

**Impact**:

"Hot" simulations capture:
- **Momentum effects**: Teams that win early in simulation have higher ratings for later games
- **Correlation in outcomes**: Winning streaks and losing streaks are more realistic
- **Path dependency**: Playoff probabilities reflect not just final record but quality of wins

"Cold" simulations assume:
- **Independence**: Each game outcome doesn't affect future game probabilities
- **Fixed strength**: Team quality doesn't change based on simulated results
- **Underestimates variance**: Won't capture "hot team" phenomena

**Why this matters**:

Late-season playoff races often feature teams that "get hot" or "collapse." Hot simulations naturally model this; cold simulations do not.

**Example**:
- Team A: 8-5 record, wins 3 straight to finish 11-6
- In hot simulation: After each simulated win, Team A's ELO rises, making subsequent wins more likely (positive feedback)
- In cold simulation: Each game is independent; no momentum effect

**Recommendation**:

Implementing hot simulations requires:
1. **Per-scenario ELO tracking**: Each of 10,000 scenarios needs its own ELO state
2. **Sequential game simulation**: Can't parallelize across games within a scenario
3. **More complex SQL/Python**: Current SQL-based simulator would need restructuring

**Implementation sketch**:
```python
for scenario_id in range(10000):
    elo_ratings = initial_elo.copy()  # Fresh copy per scenario
    for game in remaining_games:
        prob = calc_win_prob(elo_ratings[home], elo_ratings[away])
        result = random.random() < prob
        # Update ELO based on simulated result
        if result:
            elo_change = calc_elo_change(...)
            elo_ratings[home] += elo_change
            elo_ratings[away] -= elo_change
```

This would require moving simulation from SQL to Python.

**Trade-off**:
- **Performance**: Hot simulations are slower (sequential, not parallelizable within scenario)
- **Accuracy**: Hot simulations are more realistic
- **Complexity**: Hot simulations require more code

---

### 5. Special Adjustments

| Adjustment | FiveThirtyEight | nfl-data-stack | Impact |
|------------|----------------|----------------|--------|
| **Bye Week Rest** | +25 ELO points | None | ❌ Missing ~3-4% win boost |
| **Playoff Games** | EloDiff × 1.2 multiplier | None | ❌ Underestimates playoff variance |
| **Travel Distance** | 4 points per 1,000 miles | None | ❌ Missing ~1-2% for cross-country |
| **Locked Playoff Seeds** | -250 points (final week) | None | ❌ Overestimates final week results |
| **Neutral Site** | No home advantage | ✅ Handled (`neutral_site` flag) | ✅ Correct |
| **Reduced Fan Attendance** | Home adv = 33 (COVID years) | Not dynamic | ⚠️ Not relevant post-COVID |

**Analysis**:

**Bye Week Adjustment** (+25 points):
- Teams coming off bye week are more rested, prepared, healthy
- 25 points ≈ 3-4% win probability boost
- **Example**: 1550 ELO team coming off bye vs 1550 team → 53% vs 50% win probability
- **Missing in nfl-data-stack**: Would require tracking bye weeks in schedule data

**Playoff Multiplier** (1.2×):
- FiveThirtyEight multiplies EloDiff by 1.2 before calculating playoff game probabilities
- This increases the gap between favorites and underdogs
- **Rationale**: Playoff games show less upsets (better teams perform better under pressure)
- **Example**:
  - Regular season: 100 ELO gap → 64% win probability
  - Playoffs: 100 × 1.2 = 120 ELO gap → 67% win probability
- **Missing in nfl-data-stack**: Regular season simulator only; doesn't model playoff games

**Travel Distance** (4 points per 1,000 miles):
- Accounts for cross-country travel fatigue
- **Example**: Seattle to Miami (~2,700 miles) → -11 ELO points for traveling team
- **Missing in nfl-data-stack**: Would require geocoding team locations and calculating distances

**Locked Playoff Seeds** (-250 points):
- Final week of season: teams with locked playoff positions rest starters
- 250-point drop ≈ makes them extreme underdogs
- **Example**: 14-2 team with locked #1 seed vs 8-8 team fighting for playoffs
- **Missing in nfl-data-stack**: Doesn't detect or adjust for playoff scenarios

**Recommendation**:

**Priority 1 (High Impact, Low Effort)**:
- ✅ Neutral site handling: Already implemented

**Priority 2 (Medium Impact, Medium Effort)**:
- Bye week adjustment: Add `came_off_bye` flag to schedule, apply +25 points

**Priority 3 (Low Impact, High Effort)**:
- Travel distance: Requires geocoding, distance calculation
- Locked seeds: Requires playoff probability feedback loop (complex)

**Priority 4 (Not Applicable)**:
- Playoff multiplier: Only relevant if modeling playoff bracket (not current scope)
- Reduced attendance: No longer relevant post-COVID

---

### 6. Win Probability Calculation

| Component | FiveThirtyEight | nfl-data-stack | Status |
|-----------|----------------|----------------|--------|
| **Formula** | `1 / (10^(-EloDiff/400) + 1)` | `1 / (10^(-(elo_diff)/400) + 1)` | ✅ Identical |
| **Point Spread** | EloDiff / 25 | Not calculated | ⚠️ Not needed for predictions |
| **Basis Points** | Not specified | 0-10000 (Parquet), 0.0-1.0 (JSON) | ➕ Good for precision |

**Analysis**:

The core formula is identical. Both implement the standard ELO-to-probability conversion.

**Point Spread Conversion**:

FiveThirtyEight provides:
> "Divide EloDiff by 25 to estimate Vegas-style spread"

Example:
- Chiefs (1700) vs Browns (1500) with home advantage (52):
  - EloDiff = 1700 - 1500 + 52 = 252
  - Spread = 252 / 25 ≈ 10 points (Chiefs -10)

nfl-data-stack doesn't calculate spreads, but could easily add:
```sql
SELECT
  home_team,
  visiting_team,
  (home_team_elo_rating - visiting_team_elo_rating + 52) / 25.0 AS point_spread
```

**Basis Points**:

nfl-data-stack stores probabilities as integers 0-10000 in Parquet files, then converts to 0.0-1.0 for JSON output.

**Benefit**:
- Avoids floating-point precision issues in DuckDB
- 10000 basis points = 0.01% precision (sufficient for predictions)

---

### 7. Confidence Intervals

| Method | FiveThirtyEight | nfl-data-stack | Status |
|--------|----------------|----------------|--------|
| **Binary Outcomes** | Not specified | Wilson score interval | ✅ Likely better |
| **Continuous Outcomes** | Not specified | Empirical percentiles (2.5%, 97.5%) | ✅ Standard approach |
| **Displayed in UI** | No CIs shown | Yes (playoff prob, wins, seed) | ➕ More transparent |

**Analysis**:

FiveThirtyEight does not display confidence intervals in their public predictions. They show point estimates only (e.g., "75.3% playoff probability").

nfl-data-stack calculates and displays 95% confidence intervals:
- **Playoff probability**: 72.9% [72.0% - 73.7%]
- **Expected wins**: 12.3 [10.0 - 15.0]
- **Average seed**: 3.2 [1 - 6]

**Why this is better**:

Showing CIs:
- Communicates uncertainty to users
- Helps distinguish "75% ± 1%" (very confident) from "75% ± 10%" (uncertain)
- Scientifically rigorous (point estimates alone can be misleading)

**Wilson Score Interval**:

More accurate than normal approximation for proportions, especially near 0% or 100%. This is best practice for binary outcomes.

**Recommendation**:
- ✅ Keep displaying confidence intervals (this is a strength vs FiveThirtyEight)
- Consider adding interpretation guidance: "Narrow CI = high confidence"

---

### 8. Data Sources

| Source | FiveThirtyEight | nfl-data-stack | Status |
|--------|----------------|----------------|--------|
| **Game Results** | Pro-Football-Reference.com | ESPN API | ✅ Equivalent |
| **QB Stats** | ESPN Total QBR | None | ❌ Missing (no QB adjustments) |
| **Vegas Lines** | Win totals for preseason | Not used | ⚠️ Could improve preseason |
| **Team Rosters** | Not specified | Not used | ⚠️ Could enable injury tracking |

**Analysis**:

**ESPN API vs Pro-Football-Reference**:

Both are reliable sources for game results. ESPN API has advantage of real-time updates, while PFR is better for historical data.

nfl-data-stack correctly uses:
- ESPN API for in-season score collection (`collect_espn_scores.py`)
- PFR for historical data (`collect_historical_data.py`)

**Missing Data Sources**:

To implement FiveThirtyEight's full methodology, would need:
1. **QB stats**: ESPN Total QBR or play-by-play data (for VALUE formula)
2. **Vegas win totals**: For preseason calibration
3. **Injury reports**: To manually adjust for non-QB injuries
4. **Bye week schedule**: To apply +25 ELO adjustment
5. **Travel distances**: Stadium locations + distance calculation

---

## Summary: Feature Parity Matrix

| Feature Category | FiveThirtyEight | nfl-data-stack | Parity |
|-----------------|----------------|----------------|---------|
| **Core ELO System** | ✅ Full | ✅ Full | 100% |
| **Preseason Ratings** | ✅ Vegas + Mean Reversion | ⚠️ Manual | 40% |
| **QB Adjustments** | ✅ VALUE System | ❌ None | 0% |
| **Monte Carlo Sim** | ✅ Hot (dynamic ELO) | ⚠️ Cold (fixed ELO) | 60% |
| **Special Adjustments** | ✅ Bye/Playoff/Travel/Locked | ✅ Bye + Neutral | 60% |
| **Confidence Intervals** | ❌ Not shown | ✅ Wilson + Percentiles | 150% |
| **Tiebreaker Logic** | ✅ NFL rules | ✅ NFL rules (tested) | 100% |
| **Data Collection** | ✅ PFR + QBR | ✅ ESPN + PFR | 90% |

**Overall Parity: ~70%** (updated 2025-11-10)

---

## Recommendations

### Immediate (High Value, Low Effort)

1. **✅ COMPLETED: Adjust home field advantage to 48 points**:
   - Changed `nfl_elo_offset: 52` → `nfl_elo_offset: 48`
   - Better aligns with FiveThirtyEight's calibrated value
   - Date completed: 2025-11-10

2. **✅ COMPLETED: Add bye week tracking**:
   - Created `nfl_bye_weeks` model to identify teams coming off bye
   - Updated `nfl_schedules` to apply ±25 ELO adjustments
   - Configuration: `bye_week_bonus: 25` in `dbt_project.yml`
   - Correctly handles all scenarios (home off bye, visiting off bye, both off bye)
   - Date completed: 2025-11-10

3. **Document limitations**:
   - Add disclaimer: "Does not account for QB performance or injuries"
   - Explain difference from FiveThirtyEight in README

### Short-term (High Value, Medium Effort)

4. **Implement preseason mean reversion**:
   - Add script to regress ratings 1/3 toward 1505 each offseason
   - Prevents rating drift over multiple seasons
   - ~50 lines of Python code

5. **Integrate Vegas win totals** (optional preseason calibration):
   - Scrape or manually input Vegas over/under win totals
   - Convert to ELO using FiveThirtyEight's formula
   - Blend with previous season's ratings (1/3 previous + 2/3 Vegas)

### Medium-term (High Value, High Effort)

6. **Implement "hot" simulations**:
   - Refactor simulator from SQL to Python
   - Update ELO after each simulated game within a scenario
   - Expect 2-5x slower runtime but more accurate playoff probabilities
   - ~500 lines of Python code

7. **Add QB VALUE system**:
   - Integrate ESPN Total QBR or Pro-Football-Reference QB stats
   - Calculate VALUE per game using FiveThirtyEight formula
   - Apply 3.3× conversion to ELO adjustments
   - ~300 lines of Python + API integration

### Long-term (Lower Priority)

8. **Travel distance adjustments**:
   - Geocode team stadium locations
   - Calculate distances for each game
   - Apply 4 points per 1,000 miles adjustment

9. **Locked playoff seed detection**:
   - Run playoff simulations to detect clinched seeds
   - Apply -250 ELO for final week games where seed is locked
   - Complex: requires playoff probability feedback into game predictions

10. **Playoff bracket simulator**:
    - Extend to wild card, divisional, conference championship, Super Bowl
    - Apply 1.2× playoff multiplier
    - Calculate championship odds

---

## Validation: How Close Are We?

To test how closely nfl-data-stack matches FiveThirtyEight:

### Proposed Tests:

1. **Historical season replay**:
   - Load 2023 season data
   - Run both models week-by-week
   - Compare playoff probabilities at each week
   - **Expected**: 5-10 percentage point differences due to missing QB/bye/travel adjustments

2. **Game-by-game predictions**:
   - Compare win probabilities for all 2024 games
   - Calculate correlation (R²) between models
   - **Expected**: R² > 0.90 (high correlation, small systematic differences)

3. **Final playoff odds**:
   - Compare end-of-season playoff probabilities
   - Measure mean absolute error
   - **Expected**: MAE < 10 percentage points for most teams

4. **ELO rating comparison**:
   - Scrape FiveThirtyEight's published ELO ratings
   - Compare to nfl-data-stack ratings at same point in season
   - **Expected**: ±30 points difference (mostly due to QB adjustments)

### Known Sources of Divergence:

- **QB adjustments**: ±50-100 points for teams with elite/poor QB play
- **Preseason calibration**: Vegas integration improves preseason accuracy
- **Hot vs cold sims**: 3-7 percentage point differences in playoff probabilities
- **Bye weeks**: ~3% difference in specific games following bye
- **Home field advantage**: 52 vs 48 = ~1% systematic bias

**Expected Overall Accuracy**:
- Within ±10 percentage points for 80% of team playoff probabilities
- Within ±20 ELO points for 70% of team ratings (excluding QB effect)

---

## Conclusion

The nfl-data-stack implements a **solid, simplified version** of FiveThirtyEight's methodology with:

### ✅ Strengths:
- Core ELO system is nearly identical
- Confidence intervals (better than FiveThirtyEight's UI)
- Comprehensive tiebreaker logic with historical validation
- Clean, testable codebase
- Full transparency (open source)

### ⚠️ Gaps:
- No QB adjustments (biggest accuracy gap)
- Cold simulations instead of hot
- Missing preseason calibration
- No bye week / travel / playoff context adjustments

### 💡 Philosophy:
nfl-data-stack prioritizes **simplicity and transparency** over feature parity. This is a valid trade-off:
- Easier to understand and validate
- Fewer data dependencies
- Less code complexity
- Still produces reasonable predictions

### 📊 Expected Accuracy:
- **Regular season game predictions**: Within 1-2% of FiveThirtyEight (very close)
- **Playoff probabilities**: Within 5-10% of FiveThirtyEight (good, not great)
- **Teams with QB changes**: Could differ by 10-20% (significant gap)

**For most use cases, nfl-data-stack provides sufficient accuracy.** For production-grade predictions competing with Vegas or FiveThirtyEight, implementing QB adjustments and hot simulations would be the highest-impact improvements.

---

**Next Steps**:
1. Review this comparison with Michelle
2. Prioritize which enhancements (if any) to implement
3. Run historical validation tests to quantify accuracy gaps
4. Update documentation to clarify methodology differences

---

**References**:
- FiveThirtyEight Methodology: https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/
- nfl-data-stack Documentation: `/docs/statistical_methodology.md`
- ELO Rollforward Implementation: `/transform/models/nfl/prep/nfl_elo_rollforward.py`
