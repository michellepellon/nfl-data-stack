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

## License

MIT License - See LICENSE file for details

---

[duckdb]: https://duckdb.org/
[dbt]: https://www.getdbt.com/
[parquet]: https://parquet.apache.org/
[rill]: https://www.rilldata.com/
