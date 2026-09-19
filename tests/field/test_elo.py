# ABOUTME: Unit tests for the plain walk-forward Elo forecaster: the single-game update,
# ABOUTME: absence of look-ahead, season regression and franchise relocation carry-over.
import math

import polars as pl
import pytest

from nflds.forecasters import HFA, MEAN, elo_plain, elo_ratings, elo_update


def test_equal_ratings_at_neutral_site_give_even_odds():
    p, _, _ = elo_update(1505.0, 1505.0, 0.0, 24, 17)
    assert p == 0.5


def test_home_field_favours_home_team():
    p, _, _ = elo_update(1505.0, 1505.0, HFA, 24, 17)
    assert p == pytest.approx(1 / (1 + 10 ** (-48 / 400)))


@pytest.mark.parametrize("scores", [(31, 10), (10, 31), (20, 20), (17, 16)])
def test_update_is_zero_sum(scores):
    _, home, away = elo_update(1600.0, 1450.0, HFA, *scores)
    assert (home - 1600.0) + (away - 1450.0) == pytest.approx(0.0, abs=1e-9)


def test_known_home_win_update():
    p, home, away = elo_update(1600.0, 1450.0, HFA, 27, 20)
    d = 198.0
    expected_p = 1 / (1 + 10 ** (-d / 400))
    m = math.log(8) * 2.2 / (d * 0.001 + 2.2)
    assert p == pytest.approx(expected_p)
    assert home == pytest.approx(1600.0 + 20 * m * (1 - expected_p))
    assert away == pytest.approx(1450.0 - 20 * m * (1 - expected_p))


def test_upset_uses_loser_perspective_in_margin_multiplier():
    p, home, _ = elo_update(1600.0, 1450.0, HFA, 20, 27)
    m = math.log(8) * 2.2 / (-198.0 * 0.001 + 2.2)
    assert home == pytest.approx(1600.0 + 20 * m * (0 - p))


def test_tie_between_unequal_teams_moves_ratings_toward_each_other():
    p, home, away = elo_update(1600.0, 1450.0, HFA, 20, 20)
    m = 2.2 / (198.0 * 0.001 + 2.2)
    assert home == pytest.approx(1600.0 + 20 * m * (0.5 - p))
    assert home < 1600.0 and away > 1450.0


def flip_final_game(snapshot, season):
    """Return the snapshot with the chronologically last game of `season` decided the other way."""
    last = snapshot.filter(pl.col("season") == season).sort("gameday", "gametime", "game_id").row(-1, named=True)
    is_last = pl.col("game_id") == last["game_id"]
    flipped = snapshot.with_columns(
        pl.when(is_last).then(pl.col("away_score")).otherwise(pl.col("home_score")).alias("home_score"),
        pl.when(is_last).then(pl.col("home_score")).otherwise(pl.col("away_score")).alias("away_score"),
        pl.when(is_last).then(-pl.col("result")).otherwise(pl.col("result")).alias("result"),
    )
    return flipped, last


def test_no_look_ahead(snapshot):
    flipped, last = flip_final_game(snapshot, 2021)
    assert last["game_type"] == "SB" and last["result"] != 0
    before = elo_plain(snapshot).sort("game_id")
    after = elo_plain(flipped).sort("game_id")
    assert before["game_id"].equals(after["game_id"])

    through_2021 = pl.col("season") <= 2021
    assert before.filter(through_2021)["p_home"].equals(after.filter(through_2021)["p_home"])

    changed = set(
        before.join(after, on="game_id", suffix="_after")
        .filter(pl.col("p_home") != pl.col("p_home_after"))["game_id"]
    )
    for team in (last["home_team"], last["away_team"]):
        first_2022 = (
            snapshot.filter((pl.col("season") == 2022) & ((pl.col("home_team") == team) | (pl.col("away_team") == team)))
            .sort("gameday", "gametime", "game_id")["game_id"][0]
        )
        assert first_2022 in changed


def test_every_team_starts_at_the_mean_in_the_first_season(snapshot):
    ratings = elo_ratings(snapshot)
    week1 = ratings.filter((pl.col("season") == 2015) & (pl.col("week") == 1))
    assert week1.height == 16
    assert (week1["home_elo"] == MEAN).all() and (week1["away_elo"] == MEAN).all()


@pytest.mark.parametrize(
    "old, new, last_season", [("SD", "LAC", 2016), ("STL", "LA", 2015), ("OAK", "LV", 2019)]
)
def test_relocated_franchise_keeps_its_rating(snapshot, old, new, last_season):
    ratings = elo_ratings(snapshot).join(
        snapshot.select("game_id", "home_team", "away_team", "home_score", "away_score", "location"), on="game_id"
    )

    def games(team, season):
        return ratings.filter(
            (pl.col("season") == season) & ((pl.col("home_team") == team) | (pl.col("away_team") == team))
        ).sort("gameday", "gametime", "game_id")

    final = games(old, last_season).row(-1, named=True)
    hfa = 0.0 if final["location"] == "Neutral" else HFA
    _, home_after, away_after = elo_update(
        final["home_elo"], final["away_elo"], hfa, final["home_score"], final["away_score"]
    )
    rating_after = home_after if final["home_team"] == old else away_after

    opener = games(new, last_season + 1).row(0, named=True)
    carried = opener["home_elo"] if opener["home_team"] == new else opener["away_elo"]
    assert carried == pytest.approx(MEAN + (rating_after - MEAN) * 2 / 3)
    assert carried != MEAN


def test_elo_rows_cover_every_game_with_valid_probabilities(snapshot):
    rows = elo_plain(snapshot)
    assert rows.height == snapshot.height
    assert rows.columns == ["game_id", "season", "week", "forecaster", "version", "p_home"]
    assert rows["forecaster"].unique().to_list() == ["elo_plain"]
    assert rows["version"].unique().to_list() == ["elo-plain-1"]
    assert ((rows["p_home"] > 0) & (rows["p_home"] < 1)).all()
