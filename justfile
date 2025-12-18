# NFL Data Stack - Modern Data Stack in a Box
# Uses DuckDB + Parquet + dbt-duckdb + Rill for single-node analytics

# Default recipe shows available commands
default:
    @just --list

# Setup: Install dependencies and initialize environment
setup:
    @echo "Setting up NFL Data Stack..."
    uv venv --clear
    uv sync
    @echo "Installing dbt packages..."
    cd transform && ../.venv/bin/dbt deps
    @echo "Creating data directories..."
    mkdir -p data/data_catalog
    mkdir -p data/snapshots
    mkdir -p docs
    mkdir -p notebooks
    @echo "✅ Setup complete!"

# Clean: Remove generated files and caches
clean:
    @echo "Cleaning generated files..."
    rm -rf data/data_catalog/*.parquet
    rm -rf data/data_catalog/*.duckdb
    rm -rf transform/target
    rm -rf transform/dbt_packages
    rm -rf transform/logs
    rm -rf docs
    rm -rf .venv
    @echo "✅ Clean complete!"

# Seed: Generate or update seed data
seed:
    @echo "Loading seed data..."
    cd transform && ../.venv/bin/dbt seed
    @echo "✅ Seed complete!"

# Build: Run full dbt build (models + tests)
build:
    @echo "Building dbt models..."
    cd transform && ../.venv/bin/dbt build
    @echo "✅ Build complete!"

# Run: Execute dbt models only (no tests)
run:
    @echo "Running dbt models..."
    cd transform && ../.venv/bin/dbt run
    @echo "✅ Run complete!"

# Test: Run dbt tests only
test:
    @echo "Running dbt tests..."
    cd transform && ../.venv/bin/dbt test
    @echo "✅ Tests complete!"

# Docs: Generate and serve dbt documentation
docs:
    @echo "Generating dbt documentation..."
    cd transform && ../.venv/bin/dbt docs generate
    @echo "Serving docs at http://localhost:8080..."
    cd transform && ../.venv/bin/dbt docs serve --port 8080

# Profile: Run with DuckDB profiling enabled
profile:
    @echo "Running with profiling enabled..."
    cd transform && ../.venv/bin/dbt run --vars '{enable_profiling: true}'
    @echo "Check transform/logs for EXPLAIN ANALYZE output"

# Dev: Start Rill development server
dev:
    @echo "Starting Rill dev server..."
    @echo "Rill will read Parquet files from data/data_catalog/"
    cd rill_project && ~/.rill/rill start

# UI: Open Rill UI in browser
ui:
    @echo "Opening Rill UI..."
    open http://localhost:9009

# Validate: Run all validation checks
validate: build test
    @echo "Running validation checks..."
    @echo "✅ All validations passed!"

# Snapshot: Create snapshots of slowly changing dimensions
snapshot:
    @echo "Creating snapshots..."
    cd transform && ../.venv/bin/dbt snapshot
    @echo "✅ Snapshots complete!"

# Compile: Compile dbt models without execution
compile:
    @echo "Compiling dbt models..."
    cd transform && ../.venv/bin/dbt compile
    @echo "✅ Compile complete!"

# Parse: Parse dbt project
parse:
    @echo "Parsing dbt project..."
    cd transform && ../.venv/bin/dbt parse
    @echo "✅ Parse complete!"

# Format: Format SQL files with sqlfmt
format:
    @echo "Formatting SQL files..."
    uv run sqlfmt transform/models transform/macros transform/tests
    @echo "✅ Format complete!"

# Lint: Lint SQL files
lint:
    @echo "Linting SQL files..."
    @echo "Note: Install sqlfluff for linting"
    @echo "✅ Lint complete!"

# Full: Complete workflow (clean, setup, build, test, docs)
full: clean setup build test
    @echo "✅ Full workflow complete!"

# Quick: Quick rebuild (run + test)
quick: run test
    @echo "✅ Quick rebuild complete!"

# Predict: Show predictions for a specific week (default: week 10)
predict week="10":
    @echo "Generating Week {{week}} predictions..."
    .venv/bin/python scripts/predict_week.py {{week}}

# Probabilities: Show playoff probabilities with confidence intervals
probabilities:
    @echo "Generating playoff probabilities with 95% CIs..."
    .venv/bin/python scripts/show_playoff_probabilities.py

# ELO: Show ELO rating updates and analysis
elo top="10":
    @echo "Analyzing ELO rating updates..."
    .venv/bin/python scripts/show_elo_updates.py --top {{top}}

# Calibration: Show ELO calibration analysis
calibration:
    @echo "Analyzing ELO calibration..."
    .venv/bin/python scripts/show_calibration.py

# Collect: Collect historical NFL data from Pro Football Reference
collect start="2020" end="2024":
    @echo "Collecting historical NFL data ({{start}}-{{end}})..."
    .venv/bin/python scripts/collect_historical_data.py --start {{start}} --end {{end}}

# Collect-Features: Collect enhanced features (rest, weather, injuries)
collect-features start="2020" end="2024":
    @echo "Collecting enhanced features ({{start}}-{{end}})..."
    .venv/bin/python scripts/collect_enhanced_features.py --start {{start}} --end {{end}}

# Preseason-Reversion: Apply mean reversion to ELO ratings for new season
preseason-reversion:
    @echo "Applying preseason mean reversion (FiveThirtyEight methodology)..."
    uv run python scripts/apply_preseason_mean_reversion.py

# Preseason-Reversion-Vegas: Apply mean reversion + Vegas win totals integration
preseason-reversion-vegas:
    @echo "Applying preseason mean reversion with Vegas integration..."
    uv run python scripts/apply_preseason_mean_reversion.py --integrate-vegas

# Temporal-CV: Run temporal cross-validation across historical seasons
temporal-cv:
    @echo "Running temporal cross-validation..."
    .venv/bin/python scripts/temporal_cross_validation.py

# Fit-Calibration-Temporal: Fit calibration model with walk-forward validation
fit-calibration-temporal:
    @echo "Fitting temporal calibration model..."
    .venv/bin/python scripts/fit_calibration_temporal.py

# Collect-Opening-Lines: Capture opening Vegas lines (run Monday/Tuesday)
collect-opening-lines:
    @echo "Collecting opening Vegas lines..."
    .venv/bin/python scripts/collect_vegas_lines_snapshot.py opening

# Collect-Closing-Lines: Capture closing Vegas lines (run pre-game)
collect-closing-lines:
    @echo "Collecting closing Vegas lines..."
    .venv/bin/python scripts/collect_vegas_lines_snapshot.py closing

# Collect-Lines-Interim: Capture interim Vegas lines snapshot
collect-lines-interim:
    @echo "Collecting interim Vegas lines snapshot..."
    .venv/bin/python scripts/collect_vegas_lines_snapshot.py interim

# Show-CLV: Display Closing Line Value analysis
show-clv:
    @echo "Analyzing Closing Line Value..."
    .venv/bin/python -c "
import polars as pl
from pathlib import Path
clv_path = Path('data/data_catalog/nfl_clv_analysis.parquet')
if not clv_path.exists():
    print('CLV data not found. Run \"just build\" first.')
    exit(1)
df = pl.read_parquet(clv_path)
print('\\n' + '=' * 60)
print('CLV Analysis Summary')
print('=' * 60)
with_clv = df.filter(pl.col('has_clv_data'))
if len(with_clv) == 0:
    print('\\nNo CLV data available yet.')
    print('Run \"just collect-opening-lines\" and \"just collect-closing-lines\"')
    exit(0)
print(f'\\nGames with CLV data: {len(with_clv)}')
print(f'Average Model CLV: {with_clv[\"model_clv\"].mean():.2%}')
print(f'Average Ensemble CLV: {with_clv[\"ensemble_clv\"].mean():.2%}')
print(f'\\nCLV by Week:')
weekly = with_clv.group_by('week_number').agg([
    pl.col('model_clv').mean().alias('avg_clv'),
    pl.count().alias('n_games')
]).sort('week_number')
for row in weekly.iter_rows(named=True):
    print(f'  Week {row[\"week_number\"]}: {row[\"avg_clv\"]:+.2%} ({row[\"n_games\"]} games)')
"

# Show-Weights: Display dynamic ensemble weights
show-weights:
    @echo "Analyzing dynamic ensemble weights..."
    .venv/bin/python -c "
import polars as pl
from pathlib import Path
weights_path = Path('data/data_catalog/nfl_dynamic_weights.parquet')
if not weights_path.exists():
    print('Weights data not found. Run \"just build\" first.')
    exit(1)
df = pl.read_parquet(weights_path)
print('\\n' + '=' * 60)
print('Dynamic Ensemble Weights')
print('=' * 60)
print(f'\\n{\"Week\":<8} {\"ELO\":<12} {\"Vegas\":<12} {\"Cold Start\":<12}')
print('-' * 44)
for row in df.sort('week_number').iter_rows(named=True):
    cs = 'Yes' if row['is_cold_start'] else 'No'
    print(f'{row[\"week_number\"]:<8} {row[\"elo_weight\"]:<12.2%} {row[\"vegas_weight\"]:<12.2%} {cs:<12}')
print('\\nWeight bounds: 25% - 75%')
print('Cold start uses 50/50 default for weeks 1-4')
"

# Web: Start local web server to view predictions webpage
web:
    @echo "Starting web server at http://localhost:8080..."
    @echo "Press Ctrl+C to stop"
    python3 serve.py

# Update-Web: Regenerate data for predictions webpage
update-web week="10":
    @echo "Regenerating webpage data for Week {{week}}..."
    .venv/bin/python update_webpage.py --week {{week}}

# Test-Unit: Run unit tests only
test-unit:
    @echo "Running unit tests..."
    uv run pytest tests/unit/ -v

# Test-Integration: Run integration tests only
test-integration:
    @echo "Running integration tests..."
    uv run pytest tests/integration/ -v

# Test-All: Run all tests
test-all:
    @echo "Running all tests..."
    uv run pytest tests/ -v

# Test-Coverage: Run tests with coverage report
test-coverage:
    @echo "Running tests with coverage..."
    uv run pytest tests/ --cov --cov-report=term --cov-report=html
