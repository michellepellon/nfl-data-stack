# ABOUTME: Integration test for the field on the committed snapshot, seasons 2021-2025:
# ABOUTME: snapshot -> forecasters -> forecasts table -> score, checked against independent reference values.
import polars as pl
import pytest

from nflds.forecasts import build_backtest, validate
from nflds.score import score
from nflds.snapshot import SNAPSHOT_PATH, file_sha256

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def forecasts(snapshot):
    return build_backtest(snapshot, file_sha256(SNAPSHOT_PATH))


@pytest.fixture(scope="module")
def result(snapshot, forecasts):
    return score(forecasts, snapshot)


def test_backtest_table_is_valid_and_complete(snapshot, forecasts):
    validate(forecasts)
    assert set(forecasts["forecaster"].unique()) == {"market", "elo_plain"}
    assert forecasts["kind"].unique().to_list() == ["backtest"]
    assert forecasts["data_sha256"].unique().to_list() == [file_sha256(SNAPSHOT_PATH)]
    assert forecasts.filter(pl.col("forecaster") == "elo_plain").height == snapshot.height


def test_market_game_count(result):
    assert 1400 <= result["forecasters"]["market"]["n"] <= 1430
    assert result["forecasters"]["elo_plain"]["n"] == result["forecasters"]["market"]["n"]


def test_market_yards_and_brier(result):
    market = result["forecasters"]["market"]
    assert 10.4 <= market["yards"] <= 12.4
    assert 0.209 <= market["brier"] <= 0.213


def test_elo_plain_yards_and_brier(result):
    elo = result["forecasters"]["elo_plain"]
    assert 6.2 <= elo["yards"] <= 8.2
    assert 0.221 <= elo["brier"] <= 0.226


def test_elo_trails_market_with_interval_excluding_zero(result):
    gap = result["gaps"]["elo_plain"]
    assert gap["mean"] > 0
    assert gap["ci95"][0] > 0
