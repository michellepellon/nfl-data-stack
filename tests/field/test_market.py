# ABOUTME: Unit tests for the market forecaster: American odds conversion, devigging,
# ABOUTME: sign convention on real closing moneylines, and handling of missing lines.
import numpy as np
import polars as pl
import pytest

from nflds.forecasters import devig, implied_probability, market


def test_implied_probability_known_values():
    assert implied_probability(-150) == pytest.approx(150 / 250)
    assert implied_probability(130) == pytest.approx(100 / 230)
    assert implied_probability(100) == pytest.approx(0.5)
    assert implied_probability(-100) == pytest.approx(0.5)


def test_devig_known_value():
    p_home, p_away = devig(-150, 130)
    ph, pa = 150 / 250, 100 / 230
    assert p_home == pytest.approx(ph / (ph + pa), abs=1e-15)
    assert p_home == pytest.approx(0.6 / (0.6 + 0.43478260869565216), abs=1e-15)
    assert p_home + p_away == pytest.approx(1.0, abs=1e-15)


def test_devigged_probabilities_sum_to_one_for_every_real_game(snapshot):
    priced = snapshot.drop_nulls(["home_moneyline", "away_moneyline"])
    p_home, p_away = devig(priced["home_moneyline"].to_numpy(), priced["away_moneyline"].to_numpy())
    assert len(p_home) > 3000
    np.testing.assert_allclose(p_home + p_away, 1.0, atol=1e-12)
    assert ((p_home > 0) & (p_home < 1)).all()


def test_home_favourite_by_moneyline_gets_p_home_above_half(snapshot):
    rows = market(snapshot).join(snapshot, on="game_id")
    home_fav = rows.filter((pl.col("home_moneyline") < 0) & (pl.col("away_moneyline") > 0))
    away_fav = rows.filter((pl.col("home_moneyline") > 0) & (pl.col("away_moneyline") < 0))
    assert home_fav.height > 1000 and away_fav.height > 500
    assert (home_fav["p_home"] > 0.5).all()
    assert (away_fav["p_home"] < 0.5).all()


def test_market_rows_match_devig_and_skip_missing_moneylines(snapshot):
    rows = market(snapshot)
    missing = snapshot.filter(pl.col("home_moneyline").is_null() | pl.col("away_moneyline").is_null())
    assert missing.height >= 1
    assert rows.height == snapshot.height - missing.height
    assert not set(missing["game_id"]) & set(rows["game_id"])
    assert rows.columns == ["game_id", "season", "week", "forecaster", "version", "p_home"]
    assert rows["forecaster"].unique().to_list() == ["market"]
    assert rows["version"].unique().to_list() == ["market-ml-devig-1"]
    game = snapshot.filter(pl.col("game_id") == "2025_22_SEA_NE").row(0, named=True)
    expected, _ = devig(game["home_moneyline"], game["away_moneyline"])
    assert rows.filter(pl.col("game_id") == "2025_22_SEA_NE")["p_home"][0] == pytest.approx(float(expected))
