---
title: "nfl-data-stack — Codebase Memory Pack"
when: "2025-11-10"
repo: "/Users/mpellon/dev/nfl-data-stack"
stack: ["Python 3.12+", "dbt 1.10+", "DuckDB 1.3+", "Rill", "Parquet", "uv"]
assumed_goals: "Understanding data pipeline, Monte Carlo simulation, ELO rating system for refactoring and maintenance"
analyzed_by: "Claude"
confidence: "high"
---

# 0. TL;DR (50–120 words)
Single-node NFL analytics stack that ingests game data, calculates ELO ratings with margin-of-victory adjustments, runs Monte Carlo simulations (10k scenarios) for playoff probabilities with 95% confidence intervals, and serves predictions via static webpage. Data flows through dbt layers (raw→prep→simulator→analysis) materialized as Parquet files in DuckDB. Critical paths: ESPN API for real-time scores, ELO rollforward for rating updates, tiebreaker logic for playoff seeding. Runs entirely on one machine; no distributed systems. Primary risk: complex tiebreaker implementation and data freshness dependencies.

# 1. Topography (What exists)
- **Entrypoints:**
  - `scripts/collect_espn_scores.py` - Real-time score collection from ESPN API
  - `scripts/generate_full_webpage_data.py` - Generate JSON for static site
  - `scripts/hourly_update.py` - Automated hourly updates (scores + predictions)
  - `scripts/predict_week.py` - CLI for week-specific predictions
  - `serve.py` - Web server for predictions (port 8080)
  - `update_webpage.py` - Regenerate webpage data for specific week

- **Packages/Modules:**
  - `transform/models/nfl/raw/` - External Parquet sources (results, schedules, ratings, features)
  - `transform/models/nfl/prep/` - Silver layer transformations (ELO rollforward, calibration, latest ratings)
  - `transform/models/nfl/simulator/` - Monte Carlo simulation (regular season + playoffs)
  - `transform/models/nfl/analysis/` - Gold layer analytics (predictions, calibration curves, performance metrics)
  - `scripts/` - Data collection, prediction generation, validation
  - `rill_project/` - Dashboard definitions for interactive exploration
  - `data/data_catalog/` - Parquet files + DuckDB database (nflds.duckdb)
  - `data/nfl/` - Raw CSV inputs (schedules, results)

- **Key Configs:**
  - `pyproject.toml` - Python deps (dbt-duckdb, duckdb, pandas, numpy, scikit-learn, nflreadpy, sqlmesh)
  - `justfile` - Task runner (setup, build, run, test, predict, collect, web)
  - `transform/dbt_project.yml` - dbt config (layers, materialization strategy, simulation vars)
  - `transform/profiles.yml` - DuckDB connection (single file at data/data_catalog/nflds.duckdb)
  - `transform/elo_model_versions.yml` - Version tracking for ELO model changes

- **External Touchpoints:**
  - ESPN API (site.api.espn.com) - Real-time NFL scores, updated immediately post-game
  - Pro Football Reference (www.pro-football-reference.com) - Historical data
  - DuckDB file storage - All data materialized as Parquet or DuckDB tables
  - Static webpage output - JSON written to ../personal-site/portfolio/data/webpage_data.json

<!-- MEMCARD:start id=topography summary="Map of modules, entrypoints, configs" tags=structure,layout -->
**Core Architecture**:
- Bronze (raw): External Parquet sources registered as DuckDB views
- Silver (prep): Transformations including ELO rollforward (Python dbt model)
- Gold (analysis): Analytics views for dashboards and predictions
- Output: JSON for static site + Parquet for Rill dashboards

**Entrypoints by Use Case**:
- Data Collection: collect_espn_scores.py, collect_historical_data.py, collect_enhanced_features.py
- Simulation: dbt run (executes full pipeline)
- Predictions: predict_week.py, show_playoff_probabilities.py, show_elo_updates.py
- Web: generate_full_webpage_data.py, serve.py
- Validation: show_calibration.py, temporal_cross_validation.py

**Critical Files**:
- transform/models/nfl/prep/nfl_elo_rollforward.py - ELO rating updates with MOV multiplier
- transform/models/nfl/analysis/nfl_tiebreakers_optimized.py - 20k line Python model for playoff seeding
- transform/models/nfl/simulator/nfl_reg_season_simulator.sql - Monte Carlo game simulation
- transform/models/nfl/analysis/nfl_playoff_probabilities_ci.sql - Wilson CI calculation
<!-- MEMCARD:end -->

# 2. Runtime & Data Flow (How it moves)

**Lifecycle:**
1. **Init**: Setup environment (just setup → uv venv → uv sync → dbt deps)
2. **Data Collection**:
   - Run collect_espn_scores.py (fetches latest scores from ESPN API)
   - Updates data/nfl/nfl_results_2025.csv
3. **Transform**:
   - dbt run executes models in dependency order
   - register_upstream_external_models() macro creates DuckDB views for Parquet files
   - Each model writes to data/data_catalog/ as Parquet (external materialization)
4. **Simulate**:
   - nfl_reg_season_simulator.sql runs 10k Monte Carlo scenarios
   - Each scenario: random number generator → game outcomes → standings → tiebreakers
   - Aggregate: playoff probabilities, win distributions, seed distributions
5. **Output**:
   - generate_full_webpage_data.py reads Parquet files → produces webpage_data.json
   - serve.py hosts static webpage at localhost:8080
6. **Steady-State**: Hourly update (hourly_update.py) runs steps 2-5 automatically

**Pipelines/Requests:**
```
ESPN API → CSV (nfl_results_2025.csv)
           ↓
    [dbt raw layer: external Parquet sources]
           ↓
    [dbt prep layer: ELO rollforward, latest ratings]
           ↓
    [dbt simulator layer: Monte Carlo 10k scenarios]
           ↓
    [dbt analysis layer: probabilities, calibration, performance]
           ↓
    Parquet files (data/data_catalog/)
           ↓
    [Python script: generate_full_webpage_data.py]
           ↓
    JSON (webpage_data.json) → Static Site
```

**Error/Retry Patterns:**
- ESPN API: Try/except with timeout (30s), returns empty list on failure
- Parquet reads: Graceful degradation (empty DataFrames, warning logs)
- Missing scores: Predictions omit actual_home_score/actual_away_score fields (set to null)
- Idempotency: dbt models are deterministic (fixed random seed = 42); re-running produces identical results

<!-- MEMCARD:start id=flow summary="Runtime stages and main data paths" tags=runtime,dataflow -->
**Critical Data Flow Nodes**:
1. **nfl_raw_results** → nfl_latest_results (filters to latest week)
2. **nfl_raw_team_ratings** → nfl_elo_rollforward → nfl_latest_elo (sequential game-by-game updates)
3. **nfl_latest_elo** + nfl_schedules → nfl_reg_season_simulator (Monte Carlo)
4. **nfl_reg_season_end** (simulator output) → nfl_playoff_probabilities_ci (Wilson CI calculation)
5. **Parquet files** → Python scripts → webpage_data.json

**Simulation Variables** (dbt_project.yml vars):
- scenarios: 10000 (sample size)
- random_seed: 42 (reproducibility)
- nfl_elo_offset: 52 (home field advantage)
- elo_k_factor: 20 (learning rate for rating updates)
- include_actuals: true (use real results up to current week)
- latest_ratings: true (use latest ELO vs. preseason ratings)

**Mutation Points** (where data changes):
- ELO ratings: updated after each game in nfl_elo_rollforward.py
- Game results: appended to nfl_results_2025.csv by collect_espn_scores.py
- Parquet files: overwritten on each dbt run (no incremental models)
<!-- MEMCARD:end -->

# 3. Domain Model & Contracts

**Core Concepts:**
- **ELO Rating**: Numeric strength measure (~1300-1700 for NFL teams), centered around 1500
- **Home Field Advantage**: +52 ELO points (~7.5% win probability boost)
- **Margin of Victory (MOV)**: Multiplier that increases ELO changes for blowouts and upsets
  - Formula: `ln(|margin|+1) * (2.2 / (|elo_diff| * 0.001 + 2.2))`
- **Win Probability**: `1 / (1 + 10^(-(elo_home + 52 - elo_away) / 400))`
- **Monte Carlo Scenario**: Single simulation of remaining season (10k scenarios per run)
- **Wilson Score Interval**: 95% confidence interval for binary outcomes (playoff yes/no, bye yes/no)
- **Empirical Percentile Interval**: 95% CI for continuous outcomes (wins, seed) using 2.5th/97.5th percentiles
- **Tiebreaker**: NFL rules for playoff seeding when teams have same record

**Invariants (must hold):**
- ELO ratings must update in chronological order (by game_id)
- Random seed = 42 for all simulations (reproducibility requirement)
- Home field advantage applied consistently (52 points for all teams)
- Monte Carlo scenarios >= 1000 (statistical validity threshold)
- Wilson CI z-score = 1.96 (95% confidence level)
- Game results are 0-1 binary (no incomplete games in historical data)
- Tiebreakers must follow exact NFL rules (head-to-head → division → common games → conference → SoV → SoS)

**Public Contracts:**
- **webpage_data.json schema**:
  ```json
  {
    "generated_at": "ISO-8601 timestamp",
    "current_week": 1-18,
    "ratings": [{"team": str, "conf": str, "division": str, "elo_rating": float, "vegas_preseason_total": float}],
    "predictions": [{"game_id": int, "home_team": str, "visiting_team": str, "home_win_probability": 0.0-1.0, "actual_home_score": int|null, "actual_away_score": int|null}],
    "calibration": [{"bin_lower": float, "bin_upper": float, "mean_predicted": float, "mean_observed": float, "n_predictions": int}],
    "performance": [{"week_number": int, "brier_score": float, "log_loss": float, "accuracy": float}],
    "playoffs": [{"team": str, "playoff_prob_pct": float, "playoff_ci_lower_pct": float, "playoff_ci_upper_pct": float, "avg_wins": float, "wins_ci_lower": float, "wins_ci_upper": float}]
  }
  ```

- **Parquet file schemas** (enforced by dbt models):
  - nfl_ratings.parquet: team, conf, division, elo_rating, vegas_preseason_total, ingested_at
  - nfl_reg_season_simulator.parquet: game_id, week_number, home_team, visiting_team, home_team_elo_rating, visiting_team_elo_rating, home_team_win_probability (in basis points: 0-10000)
  - nfl_playoff_probabilities_ci.parquet: team, playoff_prob_pct, playoff_ci_lower_pct, playoff_ci_upper_pct, bye_prob_pct, avg_wins, wins_ci_lower, wins_ci_upper, avg_seed

- **ESPN API Contract** (unofficial, subject to change):
  - Endpoint: site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
  - Filter: status.type.name = 'STATUS_FINAL' AND status.type.state = 'post'
  - Returns: events[] with competitors[0]=home, competitors[1]=away

<!-- MEMCARD:start id=contracts summary="Invariants and external contracts" tags=contracts,invariants -->
**Critical Invariants**:
1. ELO updates MUST be sequential by game_id (order dependency)
2. Random seed MUST be 42 (reproducibility for debugging)
3. Home advantage MUST be 52 points (calibrated to 7.5% boost)
4. Actual game results MUST be complete (no partial games)
5. Week numbers MUST be 1-18 (regular season only, no playoffs in simulator)

**Breaking Changes Risk**:
- ESPN API format change (competitor order, status fields)
- NFL tiebreaker rule changes (major risk, requires code update)
- dbt external materialization behavior (upstream dbt-duckdb changes)

**Data Quality Contracts**:
- Team names MUST match across sources (ESPN API, PFR, seed data)
- Game IDs MUST be unique and chronologically increasing
- ELO ratings MUST be positive (no negative ratings)
- Probabilities MUST be in [0, 1] for JSON output (basis points 0-10000 in Parquet)
<!-- MEMCARD:end -->

# 4. Build, Run, Test

**Build:**
```bash
# Full setup (first time)
just setup

# Build dbt models (transform + materialize Parquet)
just build          # includes tests
just run            # models only, no tests

# Specific model
cd transform && ../.venv/bin/dbt run --select nfl_playoff_probabilities_ci
```

**Run Locally:**
```bash
# Prerequisites: Python 3.12+, uv installed

# 1. Collect latest scores
.venv/bin/python scripts/collect_espn_scores.py

# 2. Run dbt pipeline
cd transform && ../.venv/bin/dbt run

# 3. Generate webpage data
.venv/bin/python scripts/generate_full_webpage_data.py

# 4. Serve webpage
python3 serve.py
# → http://localhost:8080

# Or use automation
.venv/bin/python scripts/hourly_update.py
```

**Run in Prod:**
- No production environment (single-node local only)
- For deployment: cron hourly_update.py + static site hosting

**Test Strategy:**
```bash
# dbt tests (data quality)
just test

# Unit tests: Not present (gap)
# Integration tests: Not present (gap)
# E2E tests: Not present (gap)

# Manual validation scripts
.venv/bin/python scripts/show_calibration.py     # Brier score, calibration curve
.venv/bin/python scripts/show_elo_updates.py     # Rating changes by game
.venv/bin/python scripts/temporal_cross_validation.py  # Historical accuracy

# Coverage hotspots:
# - dbt tests in transform/tests/ (mostly not_null, unique, relationships)
# - No Python unit tests for ELO calculation logic
# - No tests for tiebreaker logic (20k lines, ZERO tests)
```

**CI/CD:**
- None present (manual execution only)

<!-- MEMCARD:start id=dx summary="Developer workflow commands" tags=dx,commands -->
**Common Workflows**:

1. **Update predictions for new week**:
   ```bash
   just collect                    # fetch historical data
   .venv/bin/python scripts/collect_espn_scores.py
   just run                        # dbt models
   just update-web week=11         # regenerate JSON
   just web                        # serve locally
   ```

2. **Validate model accuracy**:
   ```bash
   just calibration                # Brier score analysis
   just elo                        # Rating update history
   just temporal-cv                # Cross-validation
   ```

3. **Explore data interactively**:
   ```bash
   just dev                        # Rill dashboards
   just ui                         # Open browser to Rill
   ```

4. **Debug predictions**:
   ```bash
   just predict week=10            # CLI predictions
   just probabilities              # Playoff probabilities
   # Check Parquet files directly:
   # python -c "import pandas as pd; print(pd.read_parquet('data/data_catalog/nfl_playoff_probabilities_ci.parquet'))"
   ```

5. **Clean rebuild**:
   ```bash
   just clean                      # Remove all generated files
   just full                       # clean → setup → build → test
   ```

**Key Dependencies**:
- uv (package manager, REQUIRED for all operations)
- just (task runner, recommended but optional)
- DuckDB (embedded, installed via Python package)
- Rill CLI (optional, for dashboards only)
<!-- MEMCARD:end -->

# 5. Design Rules & Patterns

**Conventions:**
- **Naming**:
  - dbt models: `nfl_<layer>_<entity>.sql` (e.g., nfl_prep_ratings.sql)
  - Python models: Same as SQL but .py extension
  - Scripts: `<verb>_<noun>.py` (e.g., collect_espn_scores.py)
  - Parquet files: Match model names (nfl_ratings.parquet)

- **Layering** (strict dependency flow):
  1. Raw: External sources only, no transformations
  2. Prep: Cleaning, ELO calculations, feature engineering
  3. Simulator: Monte Carlo simulation logic
  4. Analysis: Aggregations, confidence intervals, metrics

- **Error Handling**:
  - External API calls: try/except with explicit error messages
  - Parquet reads: Graceful degradation (empty DataFrames, continue)
  - dbt models: Fail fast (no error handling, let dbt report)

- **Logging**:
  - Scripts: Print statements with emoji prefixes (📥, ✓, ❌, 📊)
  - dbt models: Minimal logging (rely on dbt's built-in logging)

- **Comments**:
  - ELO rollforward: Extensive docstrings explaining formulas
  - Tiebreaker logic: Almost no comments (major gap)
  - SQL models: Header comments with description, CTEs named descriptively

**Reused Patterns:**
- **Macro for ingestion timestamp**: `{{ add_ingestion_timestamp() }}` on all models
- **External materialization**: All raw/prep/simulator layers write Parquet
- **View materialization**: Analysis layer uses views for fast queries
- **Python dbt models**: For complex logic (ELO rollforward, tiebreakers)
- **Basis points**: Store probabilities as integers 0-10000 in Parquet, convert to 0.0-1.0 in Python
- **Wilson CI calculation**: Reusable SQL formula in nfl_playoff_probabilities_ci.sql

**Anti-patterns present:**
- **20k line Python model** (nfl_tiebreakers_optimized.py) with ZERO tests
- **No unit tests** for critical ELO calculation logic
- **Timestamp stored as ingested_at** but never used for incremental logic
- **Multiple CSV snapshots** (nfl_results_2025_YYYYMMDD_HHMMSS.csv) tracked in git (should be gitignored)
- **Magic numbers** hardcoded (52, 400, 2.2, 0.001 in ELO formulas; should be constants)
- **ESPN API dependency** with no fallback or circuit breaker
- **Team name mapping** scattered across multiple files (DRY violation)

<!-- MEMCARD:start id=designrules summary="Implicit rules and conventions" tags=style,architecture -->
**Implicit Rules**:
1. All probabilities are basis points (0-10000) in Parquet, decimals (0.0-1.0) in JSON
2. Game IDs are chronologically ordered (critical for ELO rollforward)
3. Week numbers 1-18 are regular season only (no playoff weeks)
4. Team names from ESPN API MUST map to PFR team codes (manual mapping)
5. Random seed 42 is sacred (changing breaks reproducibility assumptions)

**Architecture Principles**:
- **Single-node design**: No distributed systems; everything runs in one process
- **Parquet-first storage**: Intermediate results are Parquet for Rill integration
- **Deterministic simulation**: Fixed seed ensures repeatability
- **Fail-fast validation**: dbt tests catch data quality issues immediately
- **Static site output**: No server-side logic; all predictions pre-computed

**Code Organization**:
- **scripts/**: Executable Python scripts (entrypoints)
- **transform/models/**: dbt models (data transformations)
- **transform/macros/**: Reusable dbt SQL functions
- **data/data_catalog/**: Materialized Parquet + DuckDB database
- **data/nfl/**: Raw CSV inputs (version controlled)
- **rill_project/**: Dashboard definitions (separate concern)
<!-- MEMCARD:end -->

# 6. Dependency Graph (High level)

**Internal Dependencies:**
```
Raw Layer:
  nfl_raw_results
  nfl_raw_schedule
  nfl_raw_team_ratings
  nfl_raw_enhanced_features
          ↓
Prep Layer:
  nfl_latest_results ← nfl_raw_results
  nfl_schedules ← nfl_raw_schedule
  nfl_ratings ← nfl_raw_team_ratings + nfl_latest_elo
  nfl_elo_rollforward ← nfl_raw_results + nfl_raw_team_ratings
  nfl_latest_elo ← nfl_elo_rollforward
  nfl_elo_calibrated_predictions ← nfl_elo_rollforward
          ↓
Simulator Layer:
  nfl_reg_season_simulator ← nfl_schedules + nfl_ratings + nfl_random_num_gen
  nfl_reg_season_end ← nfl_reg_season_simulator
          ↓
Analysis Layer:
  nfl_playoff_probabilities_ci ← nfl_reg_season_end
  nfl_model_performance ← nfl_reg_season_simulator + nfl_latest_results
  nfl_calibration_curve ← nfl_elo_calibrated_predictions
  nfl_weekly_picks ← nfl_reg_season_simulator
  nfl_tiebreakers_optimized ← nfl_reg_season_end
```

**External Libraries:**
- **dbt-core 1.10.x** + **dbt-duckdb** - Core transformation engine
  - CRITICAL VERSION: dbt 1.10.x required for external materialization
  - Breaking changes in 1.11+ would require code updates

- **duckdb 1.3.x** - Database engine
  - PINNED: ~=1.3.0 (minor version locked)
  - Breaking changes in 1.4+ possible (SQL dialect, Python API)

- **pandas** - Data manipulation in Python scripts
  - No version pin (risky for production)
  - Used for: Parquet I/O, JSON serialization, date handling

- **numpy** - Numerical operations
  - No version pin
  - Used for: ELO calculations, random number generation (indirect)

- **scikit-learn** - Machine learning utilities
  - Version >= 1.7.2
  - Used for: Brier score calculation, calibration curve

- **nflreadpy** - NFL data reader
  - Version >= 0.1.4
  - Used for: Pro Football Reference scraping (historical data collection)

- **sqlmesh 0.88** - SQL transformation framework
  - EXACT VERSION PINNED (risky if bugs exist)
  - Currently unused (future migration from dbt?)

**Upgrade Landmines:**
- **dbt 1.11+**: External materialization API may change (requires testing)
- **duckdb 1.4+**: SQL syntax changes (PERCENTILE_CONT, external table registration)
- **pandas 3.0+**: Deprecation warnings → errors (DataFrame.append, inplace operations)
- **Python 3.13+**: No known issues, but requires-python = ">=3.12" allows 3.13+

<!-- MEMCARD:start id=deps summary="Internal & external dependencies" tags=dependencies -->
**Critical Dependency Chains**:
1. **ELO Calculation Chain**: nfl_raw_results → nfl_elo_rollforward → nfl_latest_elo → nfl_ratings → nfl_reg_season_simulator
   - Break here = no predictions

2. **Simulation Chain**: nfl_schedules + nfl_ratings → nfl_reg_season_simulator → nfl_reg_season_end → nfl_playoff_probabilities_ci
   - Break here = no playoff probabilities

3. **Webpage Chain**: Parquet files → generate_full_webpage_data.py → webpage_data.json
   - Break here = no webpage updates

**Version Constraints**:
- dbt-core: >=1.10.0, <1.11.0 (breaking changes expected in 1.11)
- duckdb: ~=1.3.0 (compatible minor versions only)
- Python: >=3.12 (requires modern type hints, match statements)

**External API Dependencies**:
- ESPN API: Unofficial, no SLA, format can change anytime
- Pro Football Reference: Rate-limited, requires respectful scraping
<!-- MEMCARD:end -->

# 7. Hotspots & Risks

| Area | Why Risky | Evidence (files/paths) | Mitigation/Safety Net |
|------|-----------|------------------------|----------------------|
| **Tiebreaker Logic** | 20k line Python model with ZERO tests, implements complex NFL rules | transform/models/nfl/analysis/nfl_tiebreakers_optimized.py | NONE - Add integration tests comparing to known playoff results |
| **ESPN API Dependency** | Unofficial API, no SLA, format changes break data collection | scripts/collect_espn_scores.py:34-51 | Add Pro Football Reference fallback, circuit breaker pattern |
| **ELO Rollforward** | Sequential game-by-game updates, incorrect order = wrong ratings | transform/models/nfl/prep/nfl_elo_rollforward.py:85-120 | Verify game_id is chronological, add dbt test for monotonic game_id |
| **Team Name Mapping** | ESPN team IDs must map to PFR team codes, breaks on expansion teams | scripts/collect_espn_scores.py:106-141 | Centralize mapping in seed data, add validation test |
| **Random Seed Dependency** | Fixed seed = deterministic but also means no sensitivity analysis | transform/dbt_project.yml:51 | Add parameterized seed testing in CI |
| **No Unit Tests** | Python models have complex logic but zero test coverage | transform/models/nfl/prep/*.py | Add pytest suite for ELO calculations, MOV multiplier edge cases |
| **Parquet Overwrites** | No incremental logic, full refresh every run (performance risk at scale) | transform/dbt_project.yml:31-39 | Add incremental materialization for large models |
| **Data Freshness** | No SLA on ESPN API updates, stale data = wrong predictions | scripts/collect_espn_scores.py | Add freshness checks (dbt-utils), alert on stale data |

<!-- MEMCARD:start id=risks summary="Where to be careful" tags=risks,hotspots -->
**Top 3 Risks**:
1. **Tiebreaker Logic Bugs**: Most likely failure mode, highest impact (wrong playoff seeds)
   - Mitigation: Add regression tests using 2020-2024 playoff results

2. **ESPN API Breakage**: Second most likely, medium impact (no updates until fixed)
   - Mitigation: Add PFR fallback, monitoring/alerting

3. **ELO Calculation Errors**: Low probability but catastrophic impact (all predictions wrong)
   - Mitigation: Add unit tests for calc_elo_diff(), validate against FiveThirtyEight results

**Performance Risks**:
- 10k scenarios × 18 weeks × 32 teams = ~5.7M game simulations per run
- Currently fast (~30s on single thread), but scales linearly with scenario count
- Tiebreaker logic is O(n²) for teams in playoff contention

**Data Quality Risks**:
- Missing game results (ESPN API down during game) → incomplete data
- Duplicate game IDs → ELO rollforward double-counts
- Null scores in completed games → wrong win/loss records
<!-- MEMCARD:end -->

# 8. Refactor Radar (Impact vs Effort)

**Scoring:** Impact 1–5 (value to user), Effort 1–5 (developer time, lower is easier)

**Top Candidates:**

1. **Add Tiebreaker Integration Tests** — Impact: 5, Effort: 3
   - **Rationale**: Highest risk area, zero test coverage, complex logic
   - **Blast radius**: transform/models/nfl/analysis/nfl_tiebreakers_optimized.py (20k lines)
   - **Safety**: Create pytest suite comparing to known 2020-2024 playoff results
   - **Done-when**:
     - Tests for all 8 tiebreaker rules (head-to-head, division, common games, etc.)
     - Validation against historical playoff seedings (2020-2024)
     - Edge cases: 3-way ties, division ties, wildcard ties

2. **Extract ELO Constants to Config** — Impact: 3, Effort: 1
   - **Rationale**: Magic numbers (52, 400, 2.2) hardcoded in multiple places, hard to tune
   - **Blast radius**:
     - transform/models/nfl/prep/nfl_elo_rollforward.py
     - transform/dbt_project.yml (add new vars)
   - **Safety**: Existing dbt tests validate output hasn't changed
   - **Done-when**:
     - All ELO constants in dbt_project.yml vars section
     - Python models read from config dict
     - Documentation updated with formula explanations

3. **Add ESPN API Fallback to PFR** — Impact: 4, Effort: 4
   - **Rationale**: ESPN API is single point of failure for data collection
   - **Blast radius**:
     - scripts/collect_espn_scores.py (add fallback logic)
     - scripts/collect_historical_data.py (refactor to be reusable)
   - **Safety**: Test both code paths, add integration test with mocked APIs
   - **Done-when**:
     - collect_espn_scores.py tries ESPN first, falls back to PFR
     - Circuit breaker pattern (3 ESPN failures → PFR for 1 hour)
     - Metrics tracked (API calls, success rate, latency)

4. **Centralize Team Name Mapping** — Impact: 3, Effort: 2
   - **Rationale**: Team name mapping scattered across scripts, breaks on expansion teams
   - **Blast radius**:
     - Create transform/data/team_mappings.csv (seed data)
     - Update collect_espn_scores.py to use seed data
   - **Safety**: Add dbt test ensuring all teams in results have mapping
   - **Done-when**:
     - Single source of truth for team name mapping
     - dbt test validates all results/schedules have valid team codes
     - Documentation for adding new teams

5. **Add Unit Tests for ELO Calculation** — Impact: 4, Effort: 2
   - **Rationale**: ELO logic is core prediction engine, no tests
   - **Blast radius**:
     - Create tests/test_elo_rollforward.py
     - Test calc_elo_diff() with known inputs/outputs
   - **Safety**: Validate against FiveThirtyEight's published ELO ratings
   - **Done-when**:
     - Tests for: even matchup, blowout, upset, tie, neutral site
     - Edge cases: max ELO diff (400+), min margin (1 point)
     - Regression test using 2024 season results vs. FiveThirtyEight

6. **Refactor 20k Line Tiebreaker Model** — Impact: 5, Effort: 5
   - **Rationale**: Monolithic Python model is unmaintainable, duplicate code
   - **Blast radius**: Full rewrite of nfl_tiebreakers_optimized.py
   - **Safety**: Extensive test suite (see #1), staged rollout (shadow mode)
   - **Done-when**:
     - Extract reusable functions (head_to_head, division_record, etc.)
     - Rule-based table-driven approach (tiebreaker_rules.csv)
     - Code reduced to <5k lines
     - All tests passing

<!-- MEMCARD:start id=refactors summary="Prioritized refactors" tags=refactor,planning -->
**Immediate (Do First)**:
- Extract ELO constants to config (low effort, reduces technical debt)
- Add unit tests for ELO calculation (high impact, medium effort)

**Short-term (Next Sprint)**:
- Add tiebreaker integration tests (highest impact, enables future refactoring)
- Centralize team name mapping (prevents production bugs)

**Long-term (Future)**:
- Add ESPN API fallback (resilience improvement)
- Refactor tiebreaker model (major effort, requires tests first)

**Performance Optimizations** (only if needed):
- Incremental materialization for large Parquet files (not currently a bottleneck)
- Parallel scenario execution (requires DuckDB threading research)
- Tiebreaker algorithm optimization (currently O(n²), could be O(n log n))
<!-- MEMCARD:end -->

# 9. Observability & Quality Gates

**Logging:**
- **Scripts**: Print statements with emoji prefixes (not structured logging)
- **dbt**: Built-in logging (INFO level by default, debug with --debug flag)
- **Gap**: No centralized logging, no log aggregation, no retention policy

**Metrics:**
- **Model Performance**: Brier score, log loss, accuracy per week
  - Stored in: nfl_model_performance.parquet
  - Threshold: Brier < 0.25 (better than random)
- **Calibration**: Mean absolute error between predicted and observed win rates
  - Stored in: nfl_calibration_curve.parquet
  - Threshold: MAE < 0.05 (5 percentage points)
- **Gap**: No real-time metrics, no alerting on degradation

**Tracing:**
- None present

**Test Gaps:**
- **Unit Tests**: ZERO for Python models (ELO, tiebreakers, calibration)
- **Integration Tests**: ZERO for end-to-end pipeline
- **dbt Tests**: Present but minimal (mostly not_null, unique)
  - Gap: No custom tests for ELO rating bounds, probability ranges, CI validity

**Suggested Sentinel Tests:**
1. **ELO Sanity Check**: All ratings between 1000-2000 (outlier detection)
2. **Probability Bounds**: All win probabilities in [0.0, 1.0] after basis point conversion
3. **CI Validity**: All confidence interval lower bounds < upper bounds
4. **Data Freshness**: Latest game result within 24 hours of current time
5. **Tiebreaker Consistency**: Compare playoff seeds to published NFL standings (historical)
6. **Simulation Convergence**: Run with 10k vs 50k scenarios, assert playoff probabilities within 1%

**Performance Budgets / SLOs:**
- **Proposed**:
  - dbt run: < 2 minutes (currently ~30 seconds, headroom for growth)
  - ESPN API: < 5 seconds (currently ~2 seconds)
  - Webpage generation: < 10 seconds (currently ~3 seconds)
  - Brier score: < 0.25 (data quality gate)
  - Test suite: < 30 seconds (when implemented)

<!-- MEMCARD:start id=quality summary="Quality levers and gaps" tags=testing,observability -->
**Current Quality Measures**:
- dbt tests (data validation)
- Manual calibration analysis (Brier score)
- Temporal cross-validation script (historical accuracy)

**Major Gaps**:
1. No automated test suite (pytest, dbt tests are minimal)
2. No CI/CD pipeline (manual execution only)
3. No monitoring/alerting (no way to detect production issues)
4. No structured logging (debugging requires print statement archaeology)
5. No performance regression tests (could break with data volume growth)

**Recommended Additions**:
- pytest suite for Python models (ELO, tiebreakers)
- dbt-utils data tests (freshness, distribution, accepted_values)
- GitHub Actions CI (run tests on PR, deploy on merge)
- Simple alerting (email/Slack on Brier score > 0.30)
- Performance benchmarks (track dbt run time, query time)
<!-- MEMCARD:end -->

# 10. Glossary (Stable Concepts)

- **ELO Rating** → Numeric team strength measure, updates after each game (1300-1700 typical range)
- **Home Field Advantage** → +52 ELO points applied to home team before win probability calculation
- **Margin of Victory (MOV)** → Point differential, used to scale ELO rating changes (blowouts matter more)
- **Monte Carlo Simulation** → Running 10,000 scenarios of remaining season to estimate probabilities
- **Wilson Score Interval** → Statistical method for 95% confidence intervals on binary outcomes (playoff yes/no)
- **Basis Points** → Probabilities stored as integers 0-10000 (10000 = 100.0%) for precision in DuckDB
- **Tiebreaker** → NFL rules for determining playoff seeds when teams have identical records
- **Brier Score** → Accuracy metric for probabilistic predictions (lower is better, <0.25 is good)
- **Calibration** → How well predicted probabilities match actual frequencies (predicted 70% should win 70% of time)
- **External Materialization** → dbt pattern where models write to Parquet files outside DuckDB database
- **Scenario** → Single simulated season outcome (10,000 scenarios = 10,000 possible futures)
- **SoV** → Strength of Victory (combined record of teams you beat, used in tiebreakers)
- **SoS** → Strength of Schedule (combined record of teams you played, used in tiebreakers)
- **K-Factor** → ELO learning rate (20 = moderate; higher = more volatile ratings)

<!-- MEMCARD:start id=glossary summary="Domain vocabulary" tags=glossary,domain -->
**Key Abbreviations**:
- PFR: Pro Football Reference (data source)
- MOV: Margin of Victory
- CI: Confidence Interval
- SoV: Strength of Victory
- SoS: Strength of Schedule
- Elo: Named after Arpad Elo (chess rating system inventor), NOT an acronym

**Units**:
- ELO ratings: Points (dimensionless, relative scale)
- Probabilities: Decimals 0.0-1.0 in JSON, integers 0-10000 in Parquet (basis points)
- Wins: Absolute count (0-18 for 18-game season)
- Seed: Playoff position (1-7 per conference, 1=best)

**NFL-Specific Terms**:
- Bye: First-round playoff bye (seeds 1-2 in each conference)
- Wild Card: Playoff teams that didn't win division (seeds 5-7)
- Division Winner: Automatic playoff berth (seeds 1-4)
<!-- MEMCARD:end -->

# 11. Quick Reference (Jump points)

- **Primary entrypoint:** `scripts/hourly_update.py` (automated pipeline)
- **Main simulation logic:** `transform/models/nfl/simulator/nfl_reg_season_simulator.sql`
- **ELO calculation:** `transform/models/nfl/prep/nfl_elo_rollforward.py:25-90`
- **Tiebreaker logic:** `transform/models/nfl/analysis/nfl_tiebreakers_optimized.py` (entire file)
- **Most critical test:** None present (MAJOR GAP)
- **Configuration root:** `transform/dbt_project.yml` (simulation parameters)
- **Parquet output location:** `data/data_catalog/`
- **Webpage JSON output:** `../personal-site/portfolio/data/webpage_data.json`

# 12. Working Theories (clearly marked)

**Theory A**: SQLMesh 0.88 dependency suggests planned migration from dbt
- **Evidence**: sqlmesh pinned in pyproject.toml but no usage found
- **Falsify**: Search for sqlmesh in codebase (git log, TODO comments)

**Theory B**: Team uses Rill exclusively for data exploration, not dashboards
- **Evidence**: Rill dashboards defined but justfile only has 'dev' and 'ui' commands
- **Falsify**: Check if Rill dashboards are actually used (last modified dates, git history)

**Theory C**: vegas_preseason_total was previously used for display, causing confusion
- **Evidence**: Comments in generate_full_webpage_data.py:65-67 explicitly warn against using it
- **Falsify**: Check git history for bugs related to vegas_preseason_total vs avg_wins

**Theory D**: 10,000 scenarios chosen based on memory constraints, not statistical rigor
- **Evidence**: Comment in dbt_project.yml:45 says "100k is safe on 8GB RAM"
- **Falsify**: Run sensitivity analysis (10k vs 50k vs 100k scenarios), compare CI widths

# 13. Open Questions

1. **Who owns this codebase in production?** (no CI/CD, manual execution only)
2. **What is the actual update cadence?** (hourly_update.py exists but unclear if running in cron)
3. **Is SQLMesh migration planned?** (dependency present but unused)
4. **Are Rill dashboards actively used?** (defined but unclear if anyone views them)
5. **What is acceptable Brier score threshold?** (code checks < 0.25 but no formal SLO)
6. **How are tiebreaker bugs discovered?** (no tests, no validation against NFL standings)
7. **What happens when ESPN API is down?** (no fallback, no alerting)
8. **Why store basis points in Parquet?** (precision? DuckDB integer performance?)
9. **Is there a plan to add tests?** (ZERO unit tests for critical ELO/tiebreaker logic)

# 14. Next 90 Minutes Plan (when I return)

1. **Add ELO unit tests** (highest value, medium effort)
   - Create tests/test_elo_rollforward.py
   - Test calc_elo_diff() with 10 edge cases (even matchup, blowout, upset, tie, neutral site)
   - Validate against known results (FiveThirtyEight published ratings)

2. **Extract ELO constants to config** (quick win, reduces tech debt)
   - Add vars to transform/dbt_project.yml (home_adv_points, elo_scale, mov_base)
   - Update nfl_elo_rollforward.py to read from config
   - Run dbt test to verify output unchanged

3. **Add tiebreaker integration test** (high impact, starts test suite)
   - Create tests/test_tiebreakers.py
   - Load 2024 playoff results as expected output
   - Run tiebreaker model, assert seeds match NFL standings
   - Document failures (may reveal existing bugs!)

---

## Appendices

### A. File Tree (trimmed)

```
nfl-data-stack/
├── README.md                        # Project overview, quick start
├── pyproject.toml                   # Python deps (dbt, duckdb, pandas, scikit-learn)
├── justfile                         # Task runner (setup, build, run, predict, web)
├── Dockerfile                       # Container setup (not actively used)
├── serve.py                         # Web server for static predictions page
├── update_webpage.py                # Regenerate webpage JSON
├── data/
│   ├── data_catalog/               # Parquet files + DuckDB database (gitignored)
│   │   └── nflds.duckdb           # Single-file database
│   └── nfl/                        # Raw CSV inputs (version controlled)
│       ├── nfl_results_2025.csv   # Current season results
│       └── nfl_results_2025_*.csv # Snapshots (should be gitignored)
├── scripts/                        # Executable Python scripts
│   ├── collect_espn_scores.py     # Real-time score collection
│   ├── generate_full_webpage_data.py  # JSON generation for static site
│   ├── hourly_update.py            # Automated hourly pipeline
│   ├── predict_week.py             # CLI predictions
│   ├── show_calibration.py         # Brier score analysis
│   ├── show_elo_updates.py         # Rating change history
│   ├── show_playoff_probabilities.py  # CLI playoff probabilities
│   ├── collect_historical_data.py  # Pro Football Reference scraper
│   └── temporal_cross_validation.py  # Historical accuracy testing
├── transform/                      # dbt project
│   ├── dbt_project.yml            # dbt config (layers, vars, materialization)
│   ├── profiles.yml               # DuckDB connection config
│   ├── elo_model_versions.yml     # Model version tracking
│   ├── models/
│   │   ├── nfl/
│   │   │   ├── raw/               # External Parquet sources
│   │   │   │   ├── nfl_raw_results.sql
│   │   │   │   ├── nfl_raw_schedule.sql
│   │   │   │   ├── nfl_raw_team_ratings.sql
│   │   │   │   └── nfl_raw_enhanced_features.sql
│   │   │   ├── prep/              # Silver layer transformations
│   │   │   │   ├── nfl_ratings.sql
│   │   │   │   ├── nfl_elo_rollforward.py  # ELO calculation (Python)
│   │   │   │   ├── nfl_latest_elo.sql
│   │   │   │   ├── nfl_schedules.sql
│   │   │   │   └── nfl_elo_calibrated_predictions.py
│   │   │   ├── simulator/         # Monte Carlo simulation
│   │   │   │   ├── nfl_reg_season_simulator.sql
│   │   │   │   └── nfl_reg_season_end.sql
│   │   │   └── analysis/          # Gold layer analytics
│   │   │       ├── nfl_playoff_probabilities_ci.sql
│   │   │       ├── nfl_model_performance.sql
│   │   │       ├── nfl_calibration_curve.sql
│   │   │       ├── nfl_weekly_picks.sql
│   │   │       └── nfl_tiebreakers_optimized.py  # 20k lines (RISKY)
│   │   ├── _sources.yml           # Source definitions
│   │   └── _nfl_docs.yml          # dbt documentation
│   ├── macros/                    # Reusable dbt SQL functions
│   ├── tests/                     # dbt data tests (minimal)
│   └── logs/                      # dbt execution logs
├── rill_project/                  # Rill dashboards (optional)
│   ├── rill.yaml
│   ├── sources/                   # Parquet source definitions
│   └── dashboards/                # Dashboard YAML specs
├── docs/                          # Project documentation
│   ├── statistical_methodology.md  # ELO, Monte Carlo, CI explanations
│   ├── feature_engineering_design.md
│   ├── data_collection_guide.md
│   └── QUICKSTART_HISTORICAL_DATA.md
└── models/                        # Empty (legacy?)
```

### B. Notable Artifacts

**Configuration:**
- `transform/dbt_project.yml` - Simulation parameters (scenarios, seed, k_factor, home_adv)
- `transform/profiles.yml` - DuckDB connection (single file database)
- `pyproject.toml` - Python dependencies and versions

**Data:**
- `data/data_catalog/*.parquet` - All model outputs (raw, prep, simulator, analysis)
- `data/data_catalog/nflds.duckdb` - DuckDB database file
- `data/nfl/nfl_results_2025.csv` - Current season game results

**Documentation:**
- `docs/statistical_methodology.md` - Comprehensive explanation of ELO, Monte Carlo, CIs
- `README.md` - Quick start guide

**Output:**
- `../personal-site/portfolio/data/webpage_data.json` - Static site data (external repo)

### C. Change Map (if proposing major refactor)

**Phase 1: Add Test Infrastructure** (Foundation)
- Week 1: Set up pytest, add ELO unit tests
- Week 2: Add tiebreaker integration tests (compare to 2020-2024 results)
- Week 3: Add dbt-utils tests (freshness, distribution, accepted_values)
- **Checkpoint**: All tests passing, baseline code coverage report

**Phase 2: Extract Configuration** (Low-risk improvements)
- Week 4: Extract ELO constants to dbt_project.yml vars
- Week 5: Centralize team name mapping to seed data
- **Checkpoint**: dbt tests passing, no behavior change

**Phase 3: Add Resilience** (Operational improvements)
- Week 6: Add ESPN API fallback to Pro Football Reference
- Week 7: Add circuit breaker pattern, retry logic
- Week 8: Add data freshness checks, alerting
- **Checkpoint**: System handles ESPN API downtime gracefully

**Phase 4: Refactor Tiebreakers** (Major effort)
- Week 9-10: Extract reusable functions from 20k line model
- Week 11-12: Implement rule-based table-driven approach
- Week 13: Shadow mode (run both old/new, compare outputs)
- Week 14: Cutover to new implementation
- **Checkpoint**: All integration tests passing, code reduced to <5k lines

**Rollback Plan**:
- Each phase is independent (can rollback to previous phase)
- Git tags at each checkpoint (phase-1-complete, phase-2-complete, etc.)
- dbt tests validate behavior unchanged (fail fast on regression)
- Shadow mode for tiebreaker refactor (compare outputs before cutover)
