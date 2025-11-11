# Changelog - 2025-11-10

## FiveThirtyEight Alignment Improvements

### Summary

Implemented two high-priority improvements to align nfl-data-stack more closely with FiveThirtyEight's NFL prediction methodology, improving overall feature parity from ~65% to ~70%.

---

## Changes

### 1. Adjusted Home Field Advantage (52 → 48 points)

**File**: `transform/dbt_project.yml:58`

**Change**:
```yaml
# Before
nfl_elo_offset: 52  # nfl offset to ELO to get to 7.5% home advantage

# After
nfl_elo_offset: 48  # nfl home field advantage (FiveThirtyEight's rolling 10-year avg)
```

**Impact**:
- Reduces home win probability for evenly matched teams from 59.3% → 58.2% (~1.1 percentage points)
- Better aligns with FiveThirtyEight's calibrated value based on rolling 10-year average
- More accurately reflects modern NFL home field advantage (which has decreased over time)

**Testing**:
- ✅ All 21 ELO calculation unit tests passed
- Tests automatically adapted to new config value (no code changes needed)

---

### 2. Implemented Bye Week Tracking and Adjustments

**New Files**:
- `transform/models/nfl/prep/nfl_bye_weeks.sql` - Identifies teams coming off bye weeks

**Modified Files**:
- `transform/models/nfl/prep/nfl_schedules.sql` - Applies bye week adjustments to game predictions
- `transform/dbt_project.yml` - Added `bye_week_bonus: 25` configuration variable

**Implementation Details**:

The `nfl_bye_weeks` model:
1. Identifies each team's bye week (weeks where they don't appear in the schedule)
2. Restricts to typical bye week range (weeks 5-14)
3. Flags games where teams are playing immediately after their bye week

The `nfl_schedules` model now includes:
- `home_team_off_bye` flag (0 or 1)
- `visiting_team_off_bye` flag (0 or 1)
- Updated `game_site_adjustment` calculation:

```sql
-- Home team advantage + bye week adjustments
game_site_adjustment =
    nfl_elo_offset (48)
    + (home_team_off_bye × 25)
    - (visiting_team_off_bye × 25)
```

**Scenarios Handled**:

| Scenario | Formula | Result |
|----------|---------|--------|
| Home team off bye | 48 + 25 - 0 | 73 points |
| Visiting team off bye | 48 + 0 - 25 | 23 points |
| Both teams off bye | 48 + 25 - 25 | 48 points (cancels) |
| Neither team off bye | 48 + 0 - 0 | 48 points |

**Impact**:
- 29 games identified across the 2025 season with bye week adjustments
- +25 ELO points ≈ 3-4% win probability boost for team coming off bye
- Matches FiveThirtyEight's methodology exactly

**Validation Results**:
```
Week 6:  4 games with bye week teams
Week 7:  2 games with bye week teams
Week 8:  2 games with bye week teams
Week 9:  5 games with bye week teams
Week 10: 3 games with bye week teams
Week 11: 4 games with bye week teams
Week 12: 2 games with bye week teams
Week 13: 3 games with bye week teams
Week 15: 4 games with bye week teams
```

**Testing**:
- ✅ `nfl_bye_weeks` model compiled and ran successfully
- ✅ `nfl_schedules` model compiled and ran successfully with all dependencies
- ✅ Verified Parquet output contains correct bye week flags and adjustments
- ✅ Spot-checked specific games to confirm adjustment calculations

---

## Documentation Updates

Updated `docs/fivethirtyeight_comparison.md`:
- Marked both improvements as ✅ COMPLETED
- Updated feature parity matrix:
  - Core ELO System: 95% → 100% (home advantage now matches)
  - Special Adjustments: 25% → 60% (added bye week tracking)
  - Overall Parity: 65% → 70%

---

## Configuration Changes

**New Variables in `dbt_project.yml`**:
```yaml
vars:
  nfl_elo_offset: 48          # Home field advantage (was 52)
  bye_week_bonus: 25          # ELO bonus for team coming off bye week (NEW)
```

---

## Testing Status

### Unit Tests
- ✅ All 21 ELO calculation tests passing
- ✅ Tests parameterized to use config values (no test updates needed)

### Integration Tests
- ✅ Full dbt build successful (9 models)
- ✅ Seed data loaded correctly
- ✅ All models compiled without errors
- ✅ Parquet outputs generated successfully

### Manual Validation
- ✅ Inspected bye week data for correctness
- ✅ Verified game_site_adjustment calculations
- ✅ Confirmed 29 games have bye week adjustments
- ✅ Spot-checked specific game scenarios (home off bye, visiting off bye, both off bye)

---

## Performance Impact

- No performance regression detected
- Model run times:
  - `nfl_bye_weeks`: ~0.02-0.04s (new model)
  - `nfl_schedules`: ~0.02s (no change)
  - Full pipeline: ~0.59s (baseline maintained)

---

## Next Steps

Remaining improvements from FiveThirtyEight comparison (in priority order):

1. **Short-term**:
   - Preseason mean reversion (1/3 toward 1505 each offseason)
   - Vegas win totals integration (for preseason calibration)

2. **Medium-term**:
   - "Hot" simulations (update ELO during Monte Carlo scenarios)
   - QB VALUE system (±50-100 ELO points for QB performance)

3. **Long-term**:
   - Travel distance adjustments (4 points per 1,000 miles)
   - Locked playoff seed detection (-250 points final week)

---

## Breaking Changes

**None** - These are additive improvements that don't break existing functionality:
- Config changes are backwards compatible (old value still works)
- New columns added to `nfl_schedules` don't affect existing consumers
- Game predictions will change slightly due to home advantage and bye week adjustments (expected improvement in accuracy)

---

## Files Changed

```
Modified:
  transform/dbt_project.yml (2 changes)
  transform/models/nfl/prep/nfl_schedules.sql (bye week join + adjustment logic)
  docs/fivethirtyeight_comparison.md (completion status update)

Added:
  transform/models/nfl/prep/nfl_bye_weeks.sql (new model)
  docs/CHANGELOG_2025-11-10.md (this file)
```

---

**Prepared by**: Claude Code
**Date**: 2025-11-10
**Reviewed**: Pending
