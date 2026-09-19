# ABOUTME: The forecasts table: one row per game per forecaster, with provenance columns,
# ABOUTME: a validation function and parquet read/write.
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from nflds.snapshot import REPO_ROOT

FORECAST_COLUMNS = [
    "game_id", "season", "week", "forecaster", "version", "p_home",
    "kind", "made_at", "data_sha256", "code_commit",
]
KINDS = ("backtest", "live")
KEY = ["game_id", "forecaster", "version", "kind"]


def code_commit() -> str:
    """Short git SHA of the package code, or 'uncommitted' when it has local edits or git is unavailable."""
    try:
        git = ["git", "-C", str(REPO_ROOT)]
        dirty = subprocess.run(
            [*git, "status", "--porcelain", "--", "src/nflds"], capture_output=True, text=True, check=True
        ).stdout.strip()
        if dirty:
            return "uncommitted"
        return subprocess.run(
            [*git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "uncommitted"


def stamp(rows: pl.DataFrame, kind: str, data_sha256: str) -> pl.DataFrame:
    """Add provenance columns to forecaster output (game_id, season, week, forecaster, version, p_home)."""
    return rows.with_columns(
        pl.lit(kind).alias("kind"),
        pl.lit(datetime.now(timezone.utc)).dt.cast_time_unit("us").alias("made_at"),
        pl.lit(data_sha256).alias("data_sha256"),
        pl.lit(code_commit()).alias("code_commit"),
    ).select(FORECAST_COLUMNS)


def validate(df: pl.DataFrame) -> pl.DataFrame:
    """Raise ValueError unless df is a well-formed forecasts table; return it unchanged."""
    missing = [c for c in FORECAST_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"forecasts table is missing columns: {missing}")
    p = df["p_home"]
    bad = df.filter(p.is_null() | p.is_nan() | (p <= 0) | (p >= 1))
    if bad.height:
        raise ValueError(
            f"{bad.height} forecast rows have p_home outside (0, 1), e.g. "
            f"{bad['game_id'][0]} / {bad['forecaster'][0]} = {bad['p_home'][0]}"
        )
    unknown = set(df["kind"].unique()) - set(KINDS)
    if unknown:
        raise ValueError(f"forecast kind must be one of {KINDS}, found {sorted(map(str, unknown))}")
    dupes = df.filter(df.select(KEY).is_duplicated())
    if dupes.height:
        raise ValueError(
            f"{dupes.height} forecast rows share a duplicate {tuple(KEY)}, e.g. {dupes.select(KEY).row(0)}"
        )
    return df


def write_forecasts(df: pl.DataFrame, path: Path) -> None:
    validate(df)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)


def read_forecasts(path: Path) -> pl.DataFrame:
    if not Path(path).exists():
        raise FileNotFoundError(f"No forecasts at {path}. Run `python -m nflds build` first.")
    return validate(pl.read_parquet(path))
