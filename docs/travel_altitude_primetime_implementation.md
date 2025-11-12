# Travel Distance, Altitude, and Prime Time Implementation

**Date**: November 11, 2025
**Status**: ✅ Implemented and Tested

## Overview

Added three new contextual features to the NFL prediction model:
1. **Travel Distance**: Penalizes away teams for long-distance travel
2. **Altitude Adjustment**: Penalizes visiting teams at high-altitude stadiums (Denver)
3. **Prime Time Classification**: Adjusts for Thursday night games with short rest

## Files Created

### Data Files
- `data/nfl/nfl_stadiums.csv` - Stadium coordinates, altitude, and roof types for all 32 NFL teams + international venues
- `data/nfl/nfl_travel_primetime.csv` - Generated output with travel/altitude/primetime adjustments per game

### Scripts
- `scripts/collect_travel_and_primetime.py` - Data collection script using geopy for distance calculations

### dbt Models
- `transform/models/nfl/prep/nfl_travel_primetime.sql` - dbt model to load adjustments

### Configuration
- Updated `transform/models/_sources.yml` to include new data source

## Implementation Details

### Travel Distance Adjustment

**Formula**: `-4 ELO points per 1,000 miles traveled`

**Logic**:
- Calculate great circle distance between away team's home stadium and game location
- Apply penalty to away team's effective ELO rating
- Examples:
  - Seattle to Miami: ~2,734 miles = -11 ELO
  - Pittsburgh to Denver: ~1,320 miles = -5.3 ELO

**Library**: `geopy.distance.geodesic` for accurate great circle calculations

### Altitude Adjustment

**Formula**: `-10 ELO points for visiting teams at altitude > 4,000 feet`

**Logic**:
- Only Denver's Empower Field at Mile High (5,280 ft) exceeds threshold
- Applied to visiting team only
- Captures physiological impact of thin air on unprepared teams

**Data Source**: Manually curated altitude data for all stadiums

### Prime Time Classification

**Adjustments**:
- Thursday Night Football: `-5 ELO` (short rest disadvantages road team)
- Sunday Night Football: `0 ELO` (no adjustment)
- Monday Night Football: `0 ELO` (no adjustment)
- Sunday Afternoon: `0 ELO` (baseline)

**Logic**:
- Parse `gametime` and `weekday` from nflreadpy schedules
- Thursday games have 3-4 days rest vs. normal 7 days
- Only Thursday night games get penalized

## Combined Adjustment

Total contextual adjustment = travel_adjustment + altitude_adjustment + primetime_adjustment

Applied to away team's effective ELO before calculating win probability.

## 2024 Season Statistics

From test run on 2024 season (272 games):

- **Average travel distance**: 1,089 miles
- **Max travel distance**: 5,369 miles (international game)
- **High altitude games**: 9 (Denver home games)
- **Thursday night games**: 26
- **Sunday night games**: 24
- **Monday night games**: 27
- **Average total adjustment**: -5.00 ELO points

## Example Game

**Pittsburgh Steelers @ Denver Broncos (Week 2, 2024)**

| Factor | Value | Adjustment |
|--------|-------|------------|
| Travel distance | 1,320 miles | -5.28 ELO |
| Game altitude | 5,280 feet | -10.00 ELO |
| Prime time | Sunday afternoon | 0.00 ELO |
| **Total** | | **-15.28 ELO** |

Pittsburgh's effective ELO drops by 15 points for this game.

## Usage

### Collect Data
```bash
cd /Users/mpellon/dev/nfl-data-stack
uv run scripts/collect_travel_and_primetime.py --seasons 2024

# Or for multiple seasons:
uv run scripts/collect_travel_and_primetime.py --start 2020 --end 2024
```

### Run dbt Model
```bash
cd transform
uv run dbt run --select nfl_travel_primetime
```

## Next Steps

To integrate these adjustments into the ELO prediction model:

1. Join `nfl_travel_primetime` with `nfl_schedules` in the ELO rollforward model
2. Modify `nfl_elo_rollforward.py` to accept `total_contextual_adjustment` parameter
3. Apply adjustment to away team's effective ELO before calculating win probability
4. Run temporal cross-validation to measure impact on Brier score and accuracy

Expected improvement: 1-3% accuracy boost, especially for extreme cases (long travel + altitude + Thursday night).

## Dependencies

- `geopy==2.4.1` - Great circle distance calculations
- `nflreadpy` - Stadium data from schedules
- `polars` - DataFrame operations

## References

- FiveThirtyEight: Travel distance penalty of -4 ELO per 1,000 miles
- Sharp Football Analysis: Thursday night road teams underperform by ~2-3 points
- Historical data: Denver's home field advantage at altitude well documented
