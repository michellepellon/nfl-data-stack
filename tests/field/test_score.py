# ABOUTME: Unit tests for score: yards identities, the Murphy decomposition of Brier,
# ABOUTME: paired gap antisymmetry, bootstrap determinism and common-game alignment.
import numpy as np
import polars as pl
import pytest

from nflds.forecasters import elo_plain, market
from nflds.score import murphy, outcomes, score

SEASONS = range(2021, 2026)


@pytest.fixture(scope="module")
def real(snapshot):
    return pl.concat([market(snapshot), elo_plain(snapshot)])


@pytest.fixture(scope="module")
def decided(snapshot):
    """The snapshot without tied games."""
    return snapshot.filter(pl.col("result") != 0)


def synthetic(games: pl.DataFrame, name: str, p_home) -> pl.DataFrame:
    return games.select("game_id", "season", "week").with_columns(
        pl.lit(name).alias("forecaster"), pl.lit(f"{name}-1").alias("version"), pl.Series("p_home", p_home)
    )


def scored_games(snapshot, forecasts):
    """Games the market covers in the scored seasons, with outcome y."""
    covered = forecasts.filter(pl.col("forecaster") == "market").select("game_id", "week")
    return outcomes(snapshot).filter(pl.col("season").is_in(list(SEASONS))).join(covered, on="game_id")


def test_outcomes_are_one_half_zero(snapshot):
    y = outcomes(snapshot)
    assert set(y["y"].unique()) == {0.0, 0.5, 1.0}
    tie = y.join(snapshot, on="game_id").filter(pl.col("y") == 0.5)
    assert (tie["result"] == 0).all() and tie.height == 10
    assert (y.join(snapshot, on="game_id").filter(pl.col("y") == 1.0)["result"] > 0).all()


def test_base_rate_forecaster_scores_exactly_zero_yards(snapshot, real):
    games = scored_games(snapshot, real)
    base = synthetic(games, "base_rate", np.full(games.height, games["y"].mean()))
    result = score(pl.concat([real, base]), snapshot)["forecasters"]["base_rate"]
    assert result["yards"] == 0.0
    assert result["bits_resolved"] == 0.0
    assert result["log_loss_bits"] == result["entropy_bits"]
    assert result["n"] == games.height


def test_near_perfect_forecaster_scores_about_100_yards(decided, real):
    games = scored_games(decided, real)
    p = np.where(games["y"].to_numpy() == 1.0, 1 - 1e-9, 1e-9)
    perfect = synthetic(games, "oracle", p)
    result = score(pl.concat([real, perfect]), decided)["forecasters"]["oracle"]
    assert result["yards"] == pytest.approx(100.0, abs=1e-5)
    assert result["yards"] < 100.0
    assert result["brier"] == pytest.approx(0.0, abs=1e-12)


def test_entropy_is_shared_and_matches_binary_entropy_of_base_rate(snapshot, real):
    result = score(real, snapshot)["forecasters"]
    ybar = scored_games(snapshot, real)["y"].mean()
    h = -(ybar * np.log2(ybar) + (1 - ybar) * np.log2(1 - ybar))
    assert result["market"]["entropy_bits"] == result["elo_plain"]["entropy_bits"] == pytest.approx(h)
    for r in result.values():
        assert r["bits_resolved"] == pytest.approx(r["entropy_bits"] - r["log_loss_bits"])
        assert r["yards"] == pytest.approx(100 * r["bits_resolved"] / r["entropy_bits"])


@pytest.mark.parametrize("name", ["market", "elo_plain"])
def test_murphy_reconstructs_brier_on_real_forecasts(snapshot, real, name):
    games = scored_games(snapshot, real).join(real.filter(pl.col("forecaster") == name), on="game_id")
    y, p = games["y"].to_numpy(), games["p_home"].to_numpy()
    reliability, resolution, uncertainty = murphy(y, p)
    brier = score(real, snapshot)["forecasters"][name]["brier"]
    assert brier == pytest.approx(np.mean((p - y) ** 2))
    assert reliability - resolution + uncertainty == pytest.approx(brier, abs=0.002)
    assert reliability >= 0 and resolution > 0


def test_murphy_is_exact_for_forecasts_constant_within_bins(snapshot, real):
    games = scored_games(snapshot, real).join(real.filter(pl.col("forecaster") == "market"), on="game_id")
    y = games["y"].to_numpy()
    p = np.floor(games["p_home"].to_numpy() * 10) / 10 + 0.05
    reliability, resolution, uncertainty = murphy(y, p)
    assert reliability - resolution + uncertainty == pytest.approx(np.mean((p - y) ** 2), abs=1e-12)


def test_murphy_weights_bins_by_games():
    y = np.array([1.0, 1.0, 1.0, 0.0])
    p = np.array([0.95, 0.95, 0.95, 0.05])
    reliability, resolution, uncertainty = murphy(y, p)
    assert reliability == pytest.approx(0.05**2)
    assert resolution == pytest.approx((3 * 0.25**2 + 1 * 0.75**2) / 4)
    assert uncertainty == pytest.approx(0.75 * 0.25)


def test_paired_gap_is_antisymmetric(snapshot, real):
    ab = score(real, snapshot, reference="market")["gaps"]["elo_plain"]
    ba = score(real, snapshot, reference="elo_plain")["gaps"]["market"]
    assert ab["mean"] == pytest.approx(-ba["mean"], abs=1e-15)
    assert ab["sd"] == pytest.approx(ba["sd"])
    assert ab["ci95"][0] == pytest.approx(-ba["ci95"][1], abs=1e-12)
    assert ab["ci95"][1] == pytest.approx(-ba["ci95"][0], abs=1e-12)
    assert ab["games_to_2p5_sigma"] == pytest.approx(ba["games_to_2p5_sigma"])
    assert ab["games_to_2p5_sigma"] == pytest.approx((2.5 * ab["sd"] / abs(ab["mean"])) ** 2)


def test_gap_mean_is_difference_of_log_losses_and_reference_has_no_gap(snapshot, real):
    result = score(real, snapshot)
    assert set(result["gaps"]) == {"elo_plain"}
    f = result["forecasters"]
    assert result["gaps"]["elo_plain"]["mean"] == pytest.approx(
        f["elo_plain"]["log_loss_bits"] - f["market"]["log_loss_bits"]
    )


def test_bootstrap_intervals_contain_point_estimates(snapshot, real):
    result = score(real, snapshot)
    for r in result["forecasters"].values():
        assert r["yards_ci95"][0] < r["yards"] < r["yards_ci95"][1]
    gap = result["gaps"]["elo_plain"]
    assert gap["ci95"][0] < gap["mean"] < gap["ci95"][1]


def test_same_seed_gives_identical_intervals_and_other_seed_differs(snapshot, real):
    a, b = score(real, snapshot), score(real, snapshot)
    assert a == b
    c = score(real, snapshot, seed=a["seed"] + 1)
    assert c["forecasters"]["market"]["yards"] == a["forecasters"]["market"]["yards"]
    assert c["forecasters"]["market"]["yards_ci95"] != a["forecasters"]["market"]["yards_ci95"]


def test_only_common_games_are_scored(snapshot, real):
    full = score(real, snapshot)["forecasters"]
    dropped = real.filter((pl.col("forecaster") == "elo_plain") & (pl.col("season") == 2023)).head(100)["game_id"]
    thinned = real.filter(~((pl.col("forecaster") == "elo_plain") & pl.col("game_id").is_in(dropped.implode())))
    partial = score(thinned, snapshot)["forecasters"]
    assert partial["market"]["n"] == partial["elo_plain"]["n"] == full["market"]["n"] - 100
    same_games = score(real.filter(~pl.col("game_id").is_in(dropped.implode())), snapshot)["forecasters"]
    assert partial == same_games


def test_seasons_argument_restricts_games(snapshot, real):
    one = score(real, snapshot, seasons=range(2022, 2023))["forecasters"]["market"]
    assert 280 <= one["n"] <= 285


def test_unknown_reference_is_a_clear_error(snapshot, real):
    with pytest.raises(ValueError, match="reference forecaster 'nobody'"):
        score(real, snapshot, reference="nobody")


def test_two_versions_of_one_forecaster_is_a_clear_error(snapshot, real):
    twin = real.filter(pl.col("forecaster") == "market").with_columns(pl.lit("market-other").alias("version"))
    with pytest.raises(ValueError, match="more than one forecast per game"):
        score(pl.concat([real, twin]), snapshot)
