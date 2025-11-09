# NFL Data Collection Guide

**Last Updated**: 2025-11-08
**Current Data**: 134 games from 2025 season
**Goal**: Expand to multiple seasons (2020-2025) for robust calibration

## Table of Contents

1. [Why More Data?](#why-more-data)
2. [Data Sources](#data-sources)
3. [Collection Methods](#collection-methods)
4. [Data Requirements](#data-requirements)
5. [Implementation Steps](#implementation-steps)
6. [Validation](#validation)

## Why More Data?

### Current Limitations

With only **134 games** (2025 season, partial):
- ✅ Brier score is good (0.2165)
- ⚠️ Calibration bins have low sample sizes (some <10 games)
- ⚠️ Extreme probability bins unreliable
- ⚠️ Cannot validate temporal stability
- ⚠️ Limited confidence in calibration metrics

### With 5 Seasons (~1,350 games)

- ✅ Each calibration bin has 100+ games
- ✅ Can validate ELO across multiple seasons
- ✅ Can test temporal drift
- ✅ Robust Brier score calculation
- ✅ Confidence intervals on calibration itself
- ✅ Can do walk-forward validation (2020→2021→2022→etc.)

## Data Sources

### Option 1: nflfastR (RECOMMENDED)

**Best for**: Historical NFL data (1999-present)

**Pros**:
- ✅ Free, open-source
- ✅ Play-by-play data included
- ✅ Well-maintained by NFL analytics community
- ✅ R package with Python bindings
- ✅ Updated weekly during season

**Cons**:
- Requires R or Python with nfl_data_py
- Large dataset (full play-by-play)

**Installation**:
```bash
uv add nfl_data_py
```

**Sample Code**:
```python
import nfl_data_py as nfl

# Get schedule data (includes scores)
seasons = [2020, 2021, 2022, 2023, 2024]
schedule = nfl.import_schedules(seasons)

# Get team info
teams = nfl.import_team_desc()

# Schedule includes:
# - game_id, season, week, gameday
# - home_team, away_team
# - home_score, away_score
# - result (point differential from home team perspective)
# - neutral site flag
```

### Option 2: Pro Football Reference Scraping

**Best for**: Historical data with custom needs

**Pros**:
- ✅ Comprehensive historical data back to 1920s
- ✅ Includes Vegas lines, weather, etc.
- ✅ Web interface for verification

**Cons**:
- ⚠️ Scraping required (use responsibly)
- ⚠️ Rate limiting needed
- ⚠️ HTML structure can change

**Libraries**:
```bash
uv add beautifulsoup4 requests pandas
```

**Sample URLs**:
- Schedule: `https://www.pro-football-reference.com/years/2024/games.htm`
- Scores: Already included in schedule page

### Option 3: ESPN API (Unofficial)

**Best for**: Recent seasons (2010-present)

**Pros**:
- ✅ JSON API (no scraping)
- ✅ Real-time updates
- ✅ Includes Vegas lines

**Cons**:
- ⚠️ Unofficial/undocumented
- ⚠️ May break without notice
- ⚠️ Rate limiting required

**Endpoint Example**:
```
http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20240901-20250131&limit=1000
```

### Option 4: FiveThirtyEight Data

**Best for**: Historical ELO ratings + scores

**Pros**:
- ✅ Includes their ELO ratings for validation
- ✅ CSV format (easy to use)
- ✅ 1920-present coverage
- ✅ Pre-calculated probabilities

**Cons**:
- Updated less frequently
- May lag current season

**Download**:
```bash
wget https://projects.fivethirtyeight.com/nfl-api/nfl_elo.csv -O data/nfl/fivethirtyeight_elo.csv
```

## Data Requirements

### Minimum Required Fields

For ELO calibration, you need:

| Field | Description | Example |
|-------|-------------|---------|
| `game_id` | Unique game identifier | `2024_01_PHI_DAL` |
| `week` | Week number | `1` |
| `season` | Season year | `2024` |
| `home_team` | Home team name | `Philadelphia Eagles` |
| `away_team` | Away team name | `Dallas Cowboys` |
| `home_score` | Home team points | `24` |
| `away_score` | Away team points | `20` |
| `neutral_site` | Boolean neutral site | `0` |

### Optional But Useful

| Field | Purpose |
|-------|---------|
| `vegas_line` | Validate against betting markets |
| `weather` | Control for conditions |
| `roof` | Indoor/outdoor games |
| `game_type` | Regular season vs playoffs |

## Collection Methods

### Method 1: nflfastR (Recommended)

**Step 1: Create collection script**

```python
# scripts/collect_historical_data.py
import nfl_data_py as nfl
import pandas as pd
from pathlib import Path

def collect_nfl_data(start_year=2020, end_year=2024):
    """Collect NFL historical data from nflfastR"""

    print(f"Collecting NFL data for {start_year}-{end_year}...")

    # Get schedule data (includes scores)
    seasons = list(range(start_year, end_year + 1))
    schedule = nfl.import_schedules(seasons)

    # Filter to regular season + playoffs
    schedule = schedule[schedule['game_type'].isin(['REG', 'WC', 'DIV', 'CON', 'SB'])]

    # Rename columns to match our schema
    schedule_clean = schedule.rename(columns={
        'week': 'Week',
        'home_team': 'HomeTeam',
        'away_team': 'AwayTeam',
        'home_score': 'HomeScore',
        'away_score': 'AwayScore',
        'neutral_site': 'NeutralSite'
    })

    # Calculate winner and loser
    schedule_clean['Winner/tie'] = schedule_clean.apply(
        lambda r: r['HomeTeam'] if r['HomeScore'] > r['AwayScore']
                 else r['AwayTeam'] if r['AwayScore'] > r['HomeScore']
                 else 'Tie',
        axis=1
    )

    schedule_clean['Loser/tie'] = schedule_clean.apply(
        lambda r: r['AwayTeam'] if r['HomeScore'] > r['AwayScore']
                 else r['HomeTeam'] if r['AwayScore'] > r['HomeScore']
                 else 'Tie',
        axis=1
    )

    schedule_clean['PtsW'] = schedule_clean.apply(
        lambda r: max(r['HomeScore'], r['AwayScore']), axis=1
    )

    schedule_clean['PtsL'] = schedule_clean.apply(
        lambda r: min(r['HomeScore'], r['AwayScore']), axis=1
    )

    # Save to CSV
    output_file = Path('data/nfl/nfl_results_historical.csv')
    schedule_clean.to_csv(output_file, index=False)

    print(f"✅ Collected {len(schedule_clean)} games")
    print(f"💾 Saved to {output_file}")

    return schedule_clean

if __name__ == "__main__":
    collect_nfl_data(2020, 2024)
```

**Step 2: Run collection**

```bash
uv add nfl_data_py
.venv/bin/python scripts/collect_historical_data.py
```

**Step 3: Update dbt source**

```yaml
# transform/models/nfl/raw/sources.yml
sources:
  - name: nfl
    tables:
      - name: nfl_results_historical
        description: "Historical NFL results from nflfastR (2020-2024)"
```

### Method 2: FiveThirtyEight (Quick Start)

**Step 1: Download their data**

```bash
cd data/nfl
wget https://projects.fivethirtyeight.com/nfl-api/nfl_elo.csv
mv nfl_elo.csv fivethirtyeight_elo.csv
```

**Step 2: Create dbt source**

```sql
-- transform/models/nfl/raw/nfl_raw_fivethirtyeight.sql
select
    season,
    date,
    team1 as home_team,
    team2 as away_team,
    elo1_pre as home_elo_pre,
    elo2_pre as away_elo_pre,
    elo_prob1 as home_win_prob_538,
    score1 as home_score,
    score2 as away_score,
    case
        when score1 > score2 then team1
        when score2 > score1 then team2
        else null
    end as winner,
    abs(score1 - score2) as margin
from {{ source('nfl', 'fivethirtyeight_elo') }}
where season >= 2020
```

**Step 3: Compare calibrations**

You can now validate YOUR ELO against FiveThirtyEight's!

## Implementation Steps

### Phase 1: Collect Data (Week 1)

1. **Choose data source** (recommend nflfastR)
2. **Create collection script** (see Method 1 above)
3. **Run collection** for 2020-2024 seasons
4. **Validate data quality**:
   ```bash
   # Check row counts
   wc -l data/nfl/nfl_results_historical.csv
   # Should be ~1,350 games (270/season × 5 seasons)

   # Check for nulls
   .venv/bin/python -c "
   import pandas as pd
   df = pd.read_csv('data/nfl/nfl_results_historical.csv')
   print(df.isnull().sum())
   "
   ```

### Phase 2: Integrate into Pipeline (Week 1-2)

1. **Update sources.yml**
   ```yaml
   sources:
     - name: nfl
       tables:
         - name: nfl_results_historical
           description: "Historical NFL results (2020-2024)"
   ```

2. **Modify nfl_latest_results.sql** to include historical data
   ```sql
   -- Option A: Union current + historical
   select * from {{ ref('nfl_results_current') }}
   union all
   select * from {{ ref('nfl_results_historical') }}

   -- Option B: Use historical as primary source
   select * from {{ source('nfl', 'nfl_results_historical') }}
   where season >= 2020
   ```

3. **Update ELO rollforward** to process by season
   ```python
   # Group by season for cleaner processing
   for season in [2020, 2021, 2022, 2023, 2024]:
       season_games = df[df['season'] == season]
       # Process games...
   ```

### Phase 3: Re-run Calibration (Week 2)

1. **Run full build**:
   ```bash
   just build
   ```

2. **Check calibration**:
   ```bash
   just calibration
   ```

3. **Expected improvements**:
   - Brier score should stabilize
   - Calibration bins have 100+ games each
   - R² should increase significantly
   - Extreme bins become reliable

### Phase 4: Temporal Validation (Week 2-3)

1. **Create walk-forward validation**:
   - Train on 2020-2022
   - Validate on 2023
   - Train on 2020-2023
   - Validate on 2024

2. **Measure temporal drift**:
   - Does K-factor need to change over time?
   - Are teams becoming more/less predictable?

## Validation Checklist

After collecting historical data:

- [ ] Total games > 1,000
- [ ] Each season has ~270 games
- [ ] No missing scores
- [ ] No missing teams
- [ ] Neutral site flags are correct
- [ ] Game IDs are unique
- [ ] Dates are in correct format
- [ ] All active teams represented

## Recommended Approach

**For immediate improvement (1-2 hours)**:
1. Use nflfastR to collect 2020-2024 data
2. Create `nfl_results_historical.csv`
3. Update source configuration
4. Re-run `just build`
5. Check calibration improvement

**For comprehensive analysis (1-2 days)**:
1. Collect data from 2015-2024 (10 seasons)
2. Implement temporal cross-validation
3. Compare against FiveThirtyEight's ELO
4. Document calibration improvements
5. Create validation dashboards in Rill

## Expected Calibration Improvements

| Metric | Current (134 games) | With 1,350 games | Improvement |
|--------|-------------------|------------------|-------------|
| Brier Score | 0.2165 | ~0.20-0.22 | More stable |
| Sample per bin | 9-29 games | 100-200 games | 10x increase |
| Calibration R² | 0.127 | >0.90 | 7x increase |
| Confidence | Low | High | Robust |

## Next Steps

1. **Decide on data source**: nflfastR recommended
2. **Create collection script**: Use template above
3. **Test with 1 season**: Validate pipeline works
4. **Expand to 5 seasons**: Get robust calibration
5. **Re-run analysis**: Compare before/after

**Estimated Time**: 2-4 hours for full historical collection and integration

Would you like me to create the collection script for you?
