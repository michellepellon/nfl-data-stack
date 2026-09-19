# ABOUTME: Pulls nflverse schedules into a pinned parquet extract with a sha256 manifest,
# ABOUTME: and loads that extract back while verifying it has not changed.
import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import polars as pl

# ponytail: repo root is found relative to this file, which holds for the editable
# install uv makes; pass explicit paths if the package is ever installed as a wheel.
REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = REPO_ROOT / "data" / "snapshots" / "nflverse_schedules_2015_2025.parquet"
SEASONS = range(2015, 2026)
COLUMNS = [
    "game_id", "season", "game_type", "week", "gameday", "gametime",
    "away_team", "home_team", "away_score", "home_score", "result", "location",
    "home_moneyline", "away_moneyline", "spread_line",
]


def manifest_path(parquet_path: Path) -> Path:
    return parquet_path.with_suffix(".manifest.json")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_snapshot(path: Path = SNAPSHOT_PATH) -> dict:
    """Download schedules from nflverse and write the parquet plus its manifest."""
    import nflreadpy

    df = nflreadpy.load_schedules(list(SEASONS)).select(COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
    manifest = {
        "sha256": file_sha256(path),
        "rows": df.height,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "nflreadpy_version": version("nflreadpy"),
    }
    manifest_path(path).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def load_snapshot(path: Path = SNAPSHOT_PATH) -> pl.DataFrame:
    """Read the pinned parquet, refusing to return data whose sha256 differs from the manifest."""
    path = Path(path)
    if not path.exists() or not manifest_path(path).exists():
        raise FileNotFoundError(
            f"Snapshot or manifest missing at {path}. Run `python -m nflds snapshot` to create it."
        )
    expected = json.loads(manifest_path(path).read_text())["sha256"]
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(
            f"Snapshot sha256 mismatch for {path}: manifest says {expected}, file is {actual}. "
            "The pinned data changed; restore it from git or re-run `python -m nflds snapshot`."
        )
    return pl.read_parquet(path)
