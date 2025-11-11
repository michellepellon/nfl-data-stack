# Preseason Mean Reversion

## Overview

Implements FiveThirtyEight's preseason ELO rating adjustment methodology to prepare team ratings for a new NFL season. This process prevents rating drift and incorporates real-world information (Vegas win totals) about offseason roster changes.

**Based on**: [FiveThirtyEight NFL Methodology](https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/)

---

## Why Mean Reversion?

After each NFL season, teams undergo significant changes:
- **Draft picks**: New talent enters the league
- **Free agency**: Players move between teams
- **Coaching changes**: New systems and strategies
- **Retirements/injuries**: Key players leave

ELO ratings from the previous season don't account for these changes. Mean reversion addresses this by:

1. **Preventing drift**: Without reversion, ratings can drift too far from the mean over multiple seasons
2. **Accounting for uncertainty**: Offseason changes create uncertainty about true team strength
3. **Regression to the mean**: Extreme performances often regress toward average in subsequent years

---

## Methodology

### Step 1: Mean Reversion (1/3 toward 1505)

After the season ends, regress each team's ELO rating 1/3 of the way toward the league mean (1505):

```
regressed_elo = old_elo - (1/3) × (old_elo - 1505)
```

**Example**:
- **Buffalo Bills** end 2024 at 1700 ELO
- Reversion: 1700 - (1/3) × (1700 - 1505) = 1700 - 65 = **1635**
- **Miami Dolphins** end 2024 at 1400 ELO
- Reversion: 1400 - (1/3) × (1400 - 1505) = 1400 + 35 = **1435**

### Step 2: Vegas Win Totals Integration (Optional)

Blend the regressed ELO with Vegas-derived ELO:

```
vegas_elo = 1505 + (vegas_wins - 8.5) × 25
preseason_elo = (1/3) × regressed_elo + (2/3) × vegas_elo
```

**Why 8.5 wins = 1505 ELO?**
- NFL teams play 17 games (2021+)
- Average team wins ~8.5 games (.500 winning percentage)
- 1505 is the league average ELO

**Why 25 points per win?**
- Calibrated by FiveThirtyEight to match historical data
- Each win above/below 8.5 = 25 ELO points

**Example** (Buffalo Bills):
- **Regressed ELO**: 1635 (from Step 1)
- **Vegas win total**: 12.0
- **Vegas ELO**: 1505 + (12.0 - 8.5) × 25 = 1592.5
- **Preseason ELO**: (1/3) × 1635 + (2/3) × 1592.5 = **1607**

---

## Usage

### Command Line

#### Basic Mean Reversion (No Vegas)
```bash
# Apply 1/3 mean reversion only
just preseason-reversion

# Or directly:
uv run python scripts/apply_preseason_mean_reversion.py
```

**Output**: `data/nfl/nfl_team_ratings_generated.csv`

#### With Vegas Win Totals
```bash
# Apply mean reversion + Vegas integration
just preseason-reversion-vegas

# Or directly:
uv run python scripts/apply_preseason_mean_reversion.py --integrate-vegas
```

**Vegas file required**: `data/nfl/nfl_team_ratings.csv` with columns `Team`, `Win Total`

#### Custom Parameters
```bash
# Custom reversion factor (e.g., 40% instead of 33.3%)
uv run python scripts/apply_preseason_mean_reversion.py --reversion-factor 0.4

# Custom mean (e.g., 1500 instead of 1505)
uv run python scripts/apply_preseason_mean_reversion.py --mean 1500

# Custom input/output files
uv run python scripts/apply_preseason_mean_reversion.py \
    --input-file data/my_ratings.parquet \
    --output-file data/my_output.csv
```

### Workflow

**When to run**: After the regular season ends, before the next season starts

1. **Complete the current season**:
   ```bash
   # Ensure all games are processed
   just run
   ```

2. **Apply mean reversion**:
   ```bash
   # Option A: Mean reversion only
   just preseason-reversion

   # Option B: With Vegas integration (recommended)
   just preseason-reversion-vegas
   ```

3. **Review the output**:
   ```bash
   # Check the generated file
   head data/nfl/nfl_team_ratings_generated.csv

   # Compare with current ratings
   diff data/nfl/nfl_team_ratings.csv data/nfl/nfl_team_ratings_generated.csv
   ```

4. **Apply the new ratings**:
   ```bash
   # Backup current ratings
   cp data/nfl/nfl_team_ratings.csv data/nfl/nfl_team_ratings_backup_2024.csv

   # Replace with new ratings
   cp data/nfl/nfl_team_ratings_generated.csv data/nfl/nfl_team_ratings.csv
   ```

5. **Rebuild models**:
   ```bash
   # Rebuild with new ratings
   just build
   ```

---

## Example Output

```
🔄 Applying Preseason Mean Reversion
   Reversion factor: 0.333
   Target mean: 1505
   Vegas integration: Yes

📥 Loading end-of-season ratings from: data/data_catalog/nfl_latest_elo.parquet
   Loaded 32 teams

🔢 Applying mean reversion (factor=0.333, mean=1505)

Sample reversion results:
               team  elo_rating_previous  elo_rating_regressed     change
 New Orleans Saints          1394.026337           1431.017558  36.991221
   Cleveland Browns          1503.275710           1503.091903  -0.183807
      Buffalo Bills          1700.000000           1635.000000 -65.000000
Philadelphia Eagles          1783.122382           1690.414921 -92.707461

📊 Integrating Vegas win totals (2/3 weight)
   Blended 32 teams with Vegas totals

Sample blending results:
               team  elo_rating_regressed  vegas_elo  elo_rating_final  Win Total
 New Orleans Saints           1431.017558     1412.5       1418.672519        4.8
      Buffalo Bills           1635.000000     1592.5       1607.000000       12.0
Philadelphia Eagles           1690.414921     1570.0       1610.138307       11.1

✅ Saved updated ratings to: data/nfl/nfl_team_ratings_generated.csv
   32 teams

📈 Summary:
   Previous ELO:  1600.0 ± 109.6
   Regressed ELO: 1568.3 ± 73.1
   Final ELO:     1526.3 ± 50.6
```

---

## Effect on Predictions

### Variance Reduction

Mean reversion reduces rating variance, pulling extreme teams closer to average:

| Stage | Mean | Std Dev | Range |
|-------|------|---------|-------|
| End of season | 1600 | 109.6 | 1394 - 1790 |
| After reversion | 1568 | 73.1 | 1431 - 1695 |
| After Vegas blend | 1526 | 50.6 | 1418 - 1610 |

**Why this matters**: Prevents over-confidence in early-season predictions

### Impact on Win Probabilities

**Before mean reversion** (End of 2024 season):
- Bills (1700) @ Dolphins (1400): 81% win probability

**After mean reversion** (Start of 2025 season):
- Bills (1607) @ Dolphins (1492): 69% win probability

**Difference**: 12 percentage points more realistic for season opener

---

## Technical Details

### Files

- **Script**: `scripts/apply_preseason_mean_reversion.py`
- **Input**: `data/data_catalog/nfl_latest_elo.parquet` (end-of-season ratings)
- **Vegas source**: `data/nfl/nfl_team_ratings.csv` (optional)
- **Output**: `data/nfl/nfl_team_ratings_generated.csv`

### Dependencies

```python
import pandas as pd
import argparse
from pathlib import Path
from datetime import datetime
```

No external API calls or network dependencies.

### Formula Details

**Mean Reversion**:
```python
def apply_mean_reversion(elo_rating, mean=1505, reversion_factor=1/3):
    return elo_rating - reversion_factor * (elo_rating - mean)
```

**Vegas Conversion**:
```python
def vegas_wins_to_elo(win_total, mean=1505):
    return mean + (win_total - 8.5) * 25
```

**Blending** (1/3 regressed + 2/3 Vegas):
```python
preseason_elo = (1/3) * regressed_elo + (2/3) * vegas_elo
```

---

## Comparison with FiveThirtyEight

| Feature | FiveThirtyEight | nfl-data-stack |
|---------|----------------|----------------|
| **Mean reversion** | 1/3 toward 1505 | ✅ Identical |
| **Vegas integration** | 2/3 weight | ✅ Identical |
| **Win-to-ELO conversion** | 25 points per win | ✅ Identical |
| **Target mean** | 1505 | ✅ Identical |
| **Automation** | Automatic | Manual (run script) |

**Feature parity**: 100% for preseason ratings

---

## FAQ

### When should I run this?
After the regular season ends (Week 18) and before the next season starts. Typically in February/March when Vegas win totals are published.

### Do I need Vegas win totals?
No. Mean reversion alone is valuable. Vegas integration is optional but recommended for better preseason accuracy.

### Where do I get Vegas win totals?
- [OddsShark](https://www.oddsshark.com/nfl/win-totals)
- [BetMGM](https://sports.betmgm.com/en/sports/football-11/betting/usa-9/nfl-35)
- [DraftKings](https://sportsbook.draftkings.com/leagues/football/nfl)

Manually enter into `data/nfl/nfl_team_ratings.csv` column `Win Total`.

### Can I change the reversion factor?
Yes, use `--reversion-factor`:
- `0.2` = 20% reversion (less regression, keep more signal)
- `0.333` = 33.3% reversion (FiveThirtyEight default)
- `0.5` = 50% reversion (more regression, more conservative)

### What about playoff teams?
All teams undergo mean reversion equally. Playoff performance is reflected in their final regular season ELO rating, which then gets regressed.

### How does this compare to other models?
Most prediction models use similar offseason adjustments:
- **FiveThirtyEight**: 1/3 reversion + 2/3 Vegas (our implementation)
- **ESPN FPI**: Regression + recruiting rankings (college)
- **DVOA**: Full reset to preseason projections
- **Elo Pure**: No reversion (ratings carry over directly)

---

## Next Steps

After implementing preseason mean reversion, the remaining FiveThirtyEight alignment items are:

1. ✅ **Preseason mean reversion** - COMPLETED
2. **"Hot" simulations** - Update ELO during Monte Carlo scenarios
3. **QB VALUE system** - ±50-100 ELO points for QB performance
4. **Travel distance** - 4 points per 1,000 miles
5. **Locked playoff seeds** - -250 points final week

---

**Last updated**: 2025-11-10
**Status**: Implemented and tested
**Next review**: Before 2025 NFL season
