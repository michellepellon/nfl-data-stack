# ABOUTME: Unit tests for the forecasts table: validation rules, provenance stamping
# ABOUTME: and the parquet round trip.
import polars as pl
import pytest

from nflds.forecasts import FORECAST_COLUMNS, read_forecasts, stamp, validate, write_forecasts


def rows(p_home=(0.6, 0.4), game_ids=("2021_01_DAL_TB", "2021_01_PHI_ATL")):
    raw = pl.DataFrame(
        {
            "game_id": list(game_ids),
            "season": [2021] * len(game_ids),
            "week": [1] * len(game_ids),
            "forecaster": ["market"] * len(game_ids),
            "version": ["market-ml-devig-1"] * len(game_ids),
            "p_home": list(p_home),
        }
    )
    return stamp(raw, kind="backtest", data_sha256="abc123")


def test_stamp_adds_provenance_columns():
    df = rows()
    assert df.columns == FORECAST_COLUMNS
    assert df["kind"].unique().to_list() == ["backtest"]
    assert df["data_sha256"].unique().to_list() == ["abc123"]
    assert df.schema["made_at"] == pl.Datetime("us", "UTC")
    commit = df["code_commit"][0]
    assert commit == "uncommitted" or (4 <= len(commit) <= 40 and int(commit, 16) >= 0)
    validate(df)


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.2, float("nan")])
def test_validate_rejects_p_home_outside_open_unit_interval(bad):
    with pytest.raises(ValueError, match="p_home"):
        validate(rows(p_home=(0.6, bad)))


def test_validate_rejects_null_p_home():
    with pytest.raises(ValueError, match="p_home"):
        validate(rows(p_home=(0.6, None)))


def test_validate_rejects_duplicate_forecast_key():
    with pytest.raises(ValueError, match="duplicate"):
        validate(rows(game_ids=("2021_01_DAL_TB", "2021_01_DAL_TB")))


def test_validate_rejects_unknown_kind():
    df = rows().with_columns(pl.lit("guess").alias("kind"))
    with pytest.raises(ValueError, match="kind"):
        validate(df)


def test_validate_rejects_missing_columns():
    with pytest.raises(ValueError, match="columns"):
        validate(rows().drop("version"))


def test_parquet_round_trip(tmp_path):
    df = rows()
    path = tmp_path / "nested" / "f.parquet"
    write_forecasts(df, path)
    assert read_forecasts(path).equals(df)


def test_write_refuses_invalid_rows(tmp_path):
    with pytest.raises(ValueError, match="p_home"):
        write_forecasts(rows(p_home=(0.6, 1.0)), tmp_path / "f.parquet")
    assert not (tmp_path / "f.parquet").exists()
