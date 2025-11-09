# NFL Data Stack

A modern, single-node analytics stack for NFL game predictions using ELO
ratings, Monte Carlo simulations, and statistical validation.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![dbt](https://img.shields.io/badge/dbt-1.10+-orange.svg)](https://www.getdbt.com/)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.3+-yellow.svg)](https://duckdb.org/)

## Overview

This project implements a complete analytics pipeline for NFL game predictions,
combining:

- **ELO Rating System** with margin-of-victory adjustments
- **Monte Carlo Simulations** (10,000 iterations) for probability estimation
- **Statistical Validation** including calibration analysis and confidence intervals
- **Modern Data Stack** using [DuckDB][duckdb], [dbt], [Parquet][parquet], and [Rill][rill]
- **Interactive Webpage** with Tufte-inspired design for exploring predictions

## Quick Start

View the predictions webpage:

```bash
# Start the web server
just web

# Or manually:
python3 serve.py
```

Then open http://localhost:8080 in your browser.

Update predictions for a new week:

```bash
# Update for Week 11
just update-web week=11

# Or manually:
python update_webpage.py --week 11
```

## License

MIT License - See LICENSE file for details

---

[duckdb]: https://duckdb.org/
[dbt]: https://www.getdbt.com/
[parquet]: https://parquet.apache.org/
[rill]: https://www.rilldata.com/
