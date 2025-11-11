# TODO: Remaining FiveThirtyEight Alignment Work

**Last Updated**: 2025-11-10
**Current Feature Parity**: 76%
**Target**: 100%

---

## Completed ✅

### High Priority (Done)
1. ✅ **Home field advantage adjustment** (52 → 48 points) - 2025-11-10
2. ✅ **Bye week tracking** (+25 ELO bonus) - 2025-11-10
3. ✅ **Preseason mean reversion** (1/3 toward 1505 + Vegas integration) - 2025-11-10

**Impact**: Improved parity from 65% → 76% (+11 percentage points)

---

## Remaining Work

### Medium-term: High Value, High Effort

#### 4. "Hot" Simulations (Not Started)
**Status**: ⏸️ Not started
**Impact**: +20% accuracy improvement for playoff probabilities
**Effort**: ~500 lines of Python, 2-3 days
**Priority**: HIGH

**What it does**:
- Update ELO ratings during Monte Carlo scenarios (not just before)
- Captures momentum effects and hot/cold streaks
- Makes playoff probability predictions more realistic

**Current state**: "Cold" simulations (fixed ELO throughout scenario)
**Target state**: "Hot" simulations (ELO updates after each simulated game)

**Implementation approach**:
1. Refactor simulator from SQL to Python
2. For each of 10,000 scenarios:
   - Initialize with current ELO ratings
   - For each remaining game:
     - Calculate win probability with current ELO
     - Simulate game outcome
     - **Update both teams' ELO based on result**
     - Use updated ELO for next game in scenario
3. Aggregate results across all scenarios

**Files to modify**:
- Create: `scripts/hot_simulation_engine.py`
- Modify: `transform/models/nfl/simulator/nfl_reg_season_simulator.sql` → Python model
- Expected performance: 2-5× slower but more accurate

**Reference**: https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/
> "We simulate the remainder of the season tens of thousands of times using the Monte Carlo method, and these 'hot' simulations allow team ratings to change after each simulated game"

---

#### 5. QB VALUE System (Not Started)
**Status**: ⏸️ Not started
**Impact**: +10-20% accuracy for teams with QB changes/injuries
**Effort**: ~300 lines + ESPN API integration, 2-3 days
**Priority**: MEDIUM-HIGH

**What it does**:
- Adjusts team ELO based on quarterback performance
- Adds ±50-100 ELO points for elite/poor QB play
- Accounts for injuries, benching, and QB changes mid-season

**FiveThirtyEight's VALUE formula**:
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

QB_Elo_Adjustment = VALUE × 3.3
```

**Update rules**:
- Individual QB rating: Updates every 10 games (90% old + 10% new)
- Team-level QB rating: Rolling average over 20 games

**Data source needed**:
- ESPN Total QBR (API access required)
- Or Pro Football Reference play-by-play data

**Implementation approach**:
1. Create QB stats collector (ESPN API or PFR scraper)
2. Calculate VALUE rating per game
3. Maintain rolling QB ratings in database
4. Adjust ELO in predictions based on starting QB

**Files to create**:
- `scripts/collect_qb_stats.py`
- `transform/models/nfl/prep/nfl_qb_value_ratings.sql`
- `transform/models/nfl/prep/nfl_elo_with_qb_adjustment.sql`

**Reference**: https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/

---

### Long-term: Lower Priority

#### 6. Travel Distance Adjustments (Not Started)
**Status**: ⏸️ Not started
**Impact**: ~1-2% accuracy improvement for cross-country games
**Effort**: ~100 lines, 1 day
**Priority**: LOW

**What it does**:
- Applies 4 ELO points per 1,000 miles traveled
- Accounts for jet lag and travel fatigue
- Most impactful for West Coast → East Coast games

**Example**:
- Seattle to Miami (~2,700 miles) = -11 ELO points for Seattle

**Implementation approach**:
1. Add stadium locations to seed data (lat/long)
2. Calculate great circle distance for each game
3. Apply adjustment: `travel_adj = (distance / 1000) × 4`
4. Incorporate into `game_site_adjustment` calculation

**Files to modify**:
- `transform/data/nfl_teams_seed.csv` (add lat/long columns)
- `transform/models/nfl/prep/nfl_schedules.sql` (add distance calculation)

---

#### 7. Locked Playoff Seed Detection (Not Started)
**Status**: ⏸️ Not started
**Impact**: ~1% accuracy improvement (only affects final week)
**Effort**: ~200 lines, 1-2 days
**Priority**: LOW

**What it does**:
- Detects when teams have clinched playoff positions before Week 18
- Applies -250 ELO penalty (resting starters)
- Only affects games where playoff seeding is already determined

**Example**:
- 14-2 team with locked #1 seed vs 8-8 team fighting for playoffs
- Without adjustment: 75% win probability
- With adjustment: 25% win probability (team is resting starters)

**Implementation approach**:
1. After Week 17 simulations, identify clinched seeds
2. Flag Week 18 games where both playoff position and opponent are locked
3. Apply -250 ELO adjustment for locked teams
4. Requires feedback loop: simulations inform playoff status, which informs Week 18 predictions

**Complexity**: Circular dependency (simulations → playoff status → simulations)

**Files to create**:
- `scripts/detect_clinched_seeds.py`
- Logic to integrate clinched status into simulator

---

## Summary by Impact

| Improvement | Impact | Effort | Priority | Status |
|-------------|--------|--------|----------|--------|
| Hot simulations | HIGH (20%) | High (3d) | HIGH | ⏸️ Not started |
| QB VALUE | MEDIUM-HIGH (10-20%) | High (3d) | MEDIUM-HIGH | ⏸️ Not started |
| Travel distance | LOW (1-2%) | Low (1d) | LOW | ⏸️ Not started |
| Locked seeds | LOW (1%) | Medium (2d) | LOW | ⏸️ Not started |

**Recommended next step**: Implement "hot" simulations (highest impact)

---

## Feature Parity Roadmap

| Milestone | Parity | Features |
|-----------|--------|----------|
| ✅ **Current** | **76%** | Core ELO + Preseason + Bye weeks |
| 🎯 Milestone 1 | 85% | + Hot simulations |
| 🎯 Milestone 2 | 95% | + QB VALUE system |
| 🎯 Milestone 3 | 100% | + Travel distance + Locked seeds |

**Estimated time to 95% parity**: 1-2 weeks (hot sims + QB VALUE)

---

## Alternative: Accept 76% Parity

**Rationale for stopping here**:
1. ✅ Core prediction accuracy is already high (within 5-10% of FiveThirtyEight)
2. ✅ Have advantages FiveThirtyEight doesn't show (confidence intervals)
3. ✅ Codebase is simpler and more maintainable without QB/hot sim complexity
4. ⚠️ QB VALUE requires ongoing data collection (maintenance burden)
5. ⚠️ Hot simulations increase runtime 2-5× (performance trade-off)

**When to implement remaining features**:
- Hot simulations: If playoff predictions are consistently 10%+ off
- QB VALUE: If a major QB injury significantly affects predictions and we can't adjust manually
- Travel/locked seeds: If competing with Vegas lines or other prediction services

---

## Documentation

- **FiveThirtyEight comparison**: `docs/fivethirtyeight_comparison.md`
- **Preseason mean reversion**: `docs/preseason_mean_reversion.md`
- **Changelog**: `docs/CHANGELOG_2025-11-10.md`
- **Statistical methodology**: `docs/statistical_methodology.md`

---

## Testing Strategy for Future Work

When implementing remaining features:

1. **Hot simulations**:
   - Compare 10k scenario results: hot vs cold
   - Validate playoff probabilities converge (50k scenarios)
   - Regression test: 2020-2024 playoff outcomes

2. **QB VALUE**:
   - Unit tests for VALUE formula
   - Compare QB adjustments to FiveThirtyEight's published numbers (if available)
   - Historical validation: How much did Aaron Rodgers' injury affect Packers' ELO?

3. **Travel distance**:
   - Verify distance calculations (spot check SEA-MIA, etc.)
   - Compare before/after for cross-country games
   - Validate 4 pts per 1,000 miles formula

4. **Locked seeds**:
   - Test with historical Week 18 games (2021-2024)
   - Ensure only teams with clinched seeds get adjustment
   - Verify no false positives (teams still playing for position)

---

**Last commit**: `6ecbea0 feat: implement preseason mean reversion with Vegas integration [AI]`
**Next session**: Implement hot simulations OR accept current 76% parity
**Decision point**: Discuss trade-offs with Michelle before proceeding
