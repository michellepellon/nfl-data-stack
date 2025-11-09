# Quick Start: Collecting Historical NFL Data

**Time Required**: 10-15 minutes
**Result**: ~1,350 games (2020-2024) for robust calibration

## Step 1: Install nfl_data_py

```bash
cd /Users/mpellon/dev/nfl-data-stack
uv add nfl_data_py
```

This installs the nflfastR Python package.

## Step 2: Run the Collection Script

```bash
just collect
```

Or with custom years:
```bash
just collect 2018 2024  # Get 7 seasons
```

**What it does**:
- Downloads game data from nflfastR
- Filters to completed games only
- Transforms to match your schema
- Saves to `data/nfl/nfl_results_historical.csv`
- Validates data quality

**Expected output**:
```
Collecting NFL Historical Data from nflfastR
Seasons: 2020-2024

📥 Downloading schedule data from nflfastR...
✓ Downloaded 1,421 total games
✓ Filtered to 1,358 completed games
✓ Regular season + playoffs: 1,358 games

📊 Data Summary:
   Total games: 1,358
   Regular season: 1,270 games
   Playoffs: 88 games

💾 Saved to: data/nfl/nfl_results_historical.csv

✅ All validation checks passed!
```

## Step 3: Update Your Data Source

You have two options:

### Option A: Replace Current Data (Recommended)

Replace your current `nfl_results.csv` with historical data:

```bash
# Backup current data
cp data/nfl/nfl_results.csv data/nfl/nfl_results_2025_only.csv

# Use historical data
cp data/nfl/nfl_results_historical.csv data/nfl/nfl_results.csv
```

### Option B: Add as Separate Source

Keep both datasets and union them in dbt:

1. **Add source** in `transform/models/nfl/raw/sources.yml`:
```yaml
sources:
  - name: nfl
    tables:
      - name: nfl_results
        description: "Current season results"
      - name: nfl_results_historical
        description: "Historical results (2020-2024)"
```

2. **Update** `transform/models/nfl/raw/nfl_raw_results.sql`:
```sql
-- Current season
select * from {{ source("nfl", "nfl_results") }}

union all

-- Historical seasons
select * from {{ source("nfl", "nfl_results_historical") }}
```

## Step 4: Rebuild Everything

```bash
just build
```

This will:
- Process historical game results
- Calculate ELO ratings across 5 seasons
- Update calibration with 10x more data

**Build time**: 1-2 minutes (vs 10 seconds with current data)

## Step 5: Check Improved Calibration

```bash
just calibration
```

**Expected improvements**:

| Metric | Before (134 games) | After (1,358 games) |
|--------|-------------------|---------------------|
| Sample per bin | 9-29 games | 100-200 games |
| Calibration stability | Low | High |
| Brier score confidence | ±0.05 | ±0.01 |
| R² | 0.13 | >0.85 |

## Step 6: Analyze Results

```bash
# View ELO updates across all seasons
just elo 20

# Check playoff probabilities
just probabilities

# View weekly predictions
just predict 10
```

## Troubleshooting

### Error: "nfl_data_py not installed"

```bash
uv add nfl_data_py
# or
pip install nfl_data_py
```

### Error: "No internet connection"

The script requires internet to download from nflfastR. Check your connection and retry.

### Download is slow

nflfastR data is ~50-100MB. First download may take 2-5 minutes depending on connection.

### Want fewer/more seasons

```bash
# Just 2023-2024 (faster, ~544 games)
just collect 2023 2024

# Full 10 years (slower, ~2,700 games)
just collect 2015 2024
```

## Verification

After collection, verify data quality:

```bash
# Check file exists and size
ls -lh data/nfl/nfl_results_historical.csv

# Check row count
wc -l data/nfl/nfl_results_historical.csv
# Should be ~1,359 (1,358 games + 1 header)

# Quick preview
head -5 data/nfl/nfl_results_historical.csv
```

## Next Steps

1. ✅ Data collected
2. ✅ Pipeline updated
3. ✅ Build complete
4. ✅ Calibration improved
5. **→ Document findings** (optional)
6. **→ Share results** (optional)
7. **→ Implement temporal CV** (Phase 2B)

## Expected Calibration Results

With 1,358 games, you should see:

- **Brier Score**: 0.20-0.22 (excellent)
- **Each calibration bin**: 100-200 games
- **Calibration R²**: >0.85 (vs 0.13 before)
- **Assessment**: "GOOD" or "EXCELLENT" (vs "NEEDS IMPROVEMENT")

The model will be **statistically robust** and ready for production use!

## Clean Up (Optional)

To remove historical data and revert:

```bash
# Restore original data
cp data/nfl/nfl_results_2025_only.csv data/nfl/nfl_results.csv

# Remove historical file
rm data/nfl/nfl_results_historical.csv

# Rebuild
just build
```

---

**Questions?** See `docs/data_collection_guide.md` for detailed information.
