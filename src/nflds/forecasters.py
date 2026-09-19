# ABOUTME: Baseline forecasters, each a pure function from the schedules snapshot to forecast rows:
# ABOUTME: the devigged closing moneyline market and a plain walk-forward Elo.
import math

import numpy as np
import polars as pl

ROW_COLUMNS = ["game_id", "season", "week", "forecaster", "version", "p_home"]

MEAN = 1505.0
HFA = 48.0
K = 20.0
SEASON_CARRY = 2 / 3  # each rating moves one third of the way back to MEAN between seasons
FRANCHISE = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def _rows(games: pl.DataFrame, forecaster: str, version: str) -> pl.DataFrame:
    return games.with_columns(
        pl.lit(forecaster).alias("forecaster"), pl.lit(version).alias("version")
    ).select(ROW_COLUMNS)


def implied_probability(odds):
    """American odds to the bookmaker's implied probability (vig included). Scalars or arrays."""
    odds = np.asarray(odds, dtype=float)
    stake = np.abs(odds)
    return np.where(odds < 0, stake, 100.0) / (stake + 100)


def devig(home_moneyline, away_moneyline):
    """Remove the vig by normalising the two implied probabilities; returns (p_home, p_away)."""
    ph, pa = implied_probability(home_moneyline), implied_probability(away_moneyline)
    return ph / (ph + pa), pa / (ph + pa)


def market(snapshot: pl.DataFrame) -> pl.DataFrame:
    """Devigged closing moneyline. Games without both moneylines get no forecast."""
    priced = snapshot.drop_nulls(["home_moneyline", "away_moneyline"])
    p_home, _ = devig(priced["home_moneyline"].to_numpy(), priced["away_moneyline"].to_numpy())
    return _rows(priced.with_columns(pl.Series("p_home", p_home)), "market", "market-ml-devig-1")


def elo_update(home: float, away: float, hfa: float, home_score: int, away_score: int):
    """The project's canonical single-game Elo update.

    Returns (pre-game home win probability, home rating after, away rating after).
    """
    d = home - away + hfa
    p = 1 / (1 + 10 ** (-d / 400))
    margin = home_score - away_score
    y = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
    w = d if y >= 0.5 else -d
    # A tie has log(0 + 1) = 0, which would freeze the ratings; it uses 1.0 so it still moves them.
    m = (math.log(abs(margin) + 1) if margin else 1.0) * 2.2 / (w * 0.001 + 2.2)
    delta = K * m * (y - p)
    return p, home + delta, away - delta


def elo_ratings(snapshot: pl.DataFrame) -> pl.DataFrame:
    """Walk forward through every game, recording the ratings and forecast held before kickoff."""
    games = snapshot.sort("season", "gameday", "gametime", "game_id")
    ratings: dict[str, float] = {}
    season = None
    out = []
    for g in games.iter_rows(named=True):
        if g["season"] != season:
            ratings = {t: MEAN + (r - MEAN) * SEASON_CARRY for t, r in ratings.items()}
            season = g["season"]
        h = FRANCHISE.get(g["home_team"], g["home_team"])
        a = FRANCHISE.get(g["away_team"], g["away_team"])
        home, away = ratings.get(h, MEAN), ratings.get(a, MEAN)
        hfa = 0.0 if g["location"] == "Neutral" else HFA
        p, ratings[h], ratings[a] = elo_update(home, away, hfa, g["home_score"], g["away_score"])
        out.append((g["game_id"], home, away, p))
    pre = pl.DataFrame(out, schema=["game_id", "home_elo", "away_elo", "p_home"], orient="row")
    return games.select("game_id", "season", "week", "gameday", "gametime").join(pre, on="game_id")


def elo_plain(snapshot: pl.DataFrame) -> pl.DataFrame:
    """Plain walk-forward Elo: every forecast uses only games that kicked off earlier."""
    return _rows(elo_ratings(snapshot), "elo_plain", "elo-plain-1")
