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

# Temporal-CV: Run temporal cross-validation across historical seasons
temporal-cv:
    @echo "Running temporal cross-validation..."
    .venv/bin/python scripts/temporal_cross_validation.py
