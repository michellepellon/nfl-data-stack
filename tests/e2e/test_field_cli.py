# ABOUTME: End-to-end tests for the `python -m nflds` command line: build then score on the
# ABOUTME: committed snapshot, a real snapshot pull into a temp directory, and error reporting.
import json
import re
import subprocess
import sys

import polars as pl
import pytest

from nflds.forecasts import read_forecasts
from nflds.snapshot import COLUMNS

pytestmark = pytest.mark.e2e


def nflds(*args):
    return subprocess.run([sys.executable, "-m", "nflds", *map(str, args)], capture_output=True, text=True)


def test_build_then_score_prints_both_forecasters_with_yards(tmp_path):
    out = tmp_path / "forecasts" / "backtest.parquet"
    build = nflds("build", "--out", out)
    assert build.returncode == 0, build.stderr
    assert build.stderr == ""
    assert str(out) in build.stdout
    assert set(read_forecasts(out)["forecaster"].unique()) == {"market", "elo_plain"}

    score = nflds("score", "--forecasts", out)
    assert score.returncode == 0, score.stderr
    assert score.stderr == ""
    lines = score.stdout.splitlines()
    assert "yards" in lines[1]
    rows = {line.split()[0]: line for line in lines[2:4]}
    assert set(rows) == {"market", "elo_plain"}
    market_yards = float(rows["market"].split()[3])
    elo_yards = float(rows["elo_plain"].split()[3])
    assert 10.4 <= market_yards <= 12.4
    assert 6.2 <= elo_yards <= 8.2
    assert re.search(r"^elo_plain\s+\+0\.\d+ .*games to 2\.5 sigma", score.stdout, re.MULTILINE)


def test_score_honours_seasons_and_reference(tmp_path):
    out = tmp_path / "backtest.parquet"
    assert nflds("build", "--out", out).returncode == 0
    score = nflds("score", "--forecasts", out, "--seasons", "2022-2023", "--reference", "elo_plain")
    assert score.returncode == 0, score.stderr
    assert "Seasons 2022-2023" in score.stdout
    assert re.search(r"^market\s+-0\.\d+", score.stdout, re.MULTILINE)


def test_score_without_forecasts_fails_with_a_clear_message(tmp_path):
    score = nflds("score", "--forecasts", tmp_path / "missing.parquet")
    assert score.returncode == 1
    assert "error:" in score.stderr and "python -m nflds build" in score.stderr
    assert "Traceback" not in score.stderr


def test_bad_seasons_argument_is_rejected(tmp_path):
    score = nflds("score", "--seasons", "lately")
    assert score.returncode == 2
    assert "START-END" in score.stderr


def test_help_lists_the_three_commands():
    result = nflds("--help")
    assert result.returncode == 0
    for command in ("snapshot", "build", "score"):
        assert command in result.stdout


@pytest.mark.slow
def test_snapshot_pulls_real_nflverse_data_into_a_given_path(tmp_path):
    path = tmp_path / "schedules.parquet"
    result = nflds("snapshot", "--path", path)
    assert result.returncode == 0, result.stderr
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    df = pl.read_parquet(path)
    assert df.columns == COLUMNS
    assert manifest["rows"] == df.height >= 3028
    assert manifest["sha256"] in result.stdout
