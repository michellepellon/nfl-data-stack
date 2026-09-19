# ABOUTME: Scores forecasters on identical games: log loss in bits, yards (share of the base-rate
# ABOUTME: entropy resolved), Brier, bootstrap intervals and paired gaps against a reference forecaster.
import numpy as np
import polars as pl

DEFAULT_SEASONS = range(2021, 2026)
DRAWS = 2000
SEED = 20150910


def outcomes(snapshot: pl.DataFrame) -> pl.DataFrame:
    """Played games with y = 1 (home win), 0 (home loss) or 0.5 (tie)."""
    return snapshot.drop_nulls("result").select(
        "game_id", "season", (pl.col("result").sign() / 2 + 0.5).alias("y")
    )


def log_loss_bits(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Per-game log loss in bits; broadcasts, so p may be a constant."""
    return -(y * np.log2(p) + (1 - y) * np.log2(1 - p))


def murphy(y: np.ndarray, p: np.ndarray, bins: int = 10) -> tuple[float, float, float]:
    """Murphy decomposition over equal-width bins: (reliability, resolution, uncertainty).

    Bins are weighted by their game counts (sums over games, not averages of bin values), and
    uncertainty is the variance of y, which equals ybar * (1 - ybar) when there are no ties.
    Brier = reliability - resolution + uncertainty, exactly when forecasts are constant within bins.
    """
    which = np.minimum((p * bins).astype(int), bins - 1)
    n_k = np.bincount(which, minlength=bins)
    used = n_k > 0
    p_k = np.bincount(which, weights=p, minlength=bins)[used] / n_k[used]
    y_k = np.bincount(which, weights=y, minlength=bins)[used] / n_k[used]
    ybar = y.mean()
    reliability = np.sum(n_k[used] * (p_k - y_k) ** 2) / len(y)
    resolution = np.sum(n_k[used] * (y_k - ybar) ** 2) / len(y)
    return float(reliability), float(resolution), float(np.mean((y - ybar) ** 2))


def _ci95(values: np.ndarray) -> tuple[float, float]:
    lo, hi = np.percentile(values, [2.5, 97.5])
    return float(lo), float(hi)


def score(
    forecasts: pl.DataFrame,
    snapshot: pl.DataFrame,
    seasons=DEFAULT_SEASONS,
    reference: str = "market",
    draws: int = DRAWS,
    seed: int = SEED,
) -> dict:
    """Score every forecaster in `forecasts` on the games that all of them forecast.

    Returns {"n", "seed", "forecasters": {name: metrics}, "gaps": {name: paired gap vs reference}}.
    A positive gap means the forecaster loses more bits per game than the reference.
    """
    names = sorted(forecasts["forecaster"].unique())
    if reference not in names:
        raise ValueError(f"reference forecaster '{reference}' has no forecasts; found {names}")
    if forecasts.select("game_id", "forecaster").is_duplicated().any():
        raise ValueError(
            "a forecaster has more than one forecast per game; filter to one version and kind before scoring"
        )
    wide = forecasts.pivot(on="forecaster", index="game_id", values="p_home").drop_nulls()
    games = (
        outcomes(snapshot).filter(pl.col("season").is_in(list(seasons))).join(wide, on="game_id").sort("game_id")
    )
    n = games.height
    if n == 0:
        raise ValueError(f"no played games in seasons {list(seasons)} are forecast by all of {names}")

    y = games["y"].to_numpy()
    entropy = float(log_loss_bits(y, y.mean()).mean())
    idx = np.random.default_rng(seed).integers(0, n, size=(draws, n))
    ybar_b = y[idx].mean(axis=1)
    entropy_b = log_loss_bits(ybar_b, ybar_b)

    losses = {name: log_loss_bits(y, games[name].to_numpy()) for name in names}
    result = {"n": n, "seed": seed, "forecasters": {}, "gaps": {}}
    for name in names:
        p, loss = games[name].to_numpy(), losses[name]
        log_loss = float(loss.mean())
        result["forecasters"][name] = {
            "n": n,
            "log_loss_bits": log_loss,
            "entropy_bits": entropy,
            "bits_resolved": entropy - log_loss,
            "yards": 100 * (entropy - log_loss) / entropy,
            "yards_ci95": _ci95(100 * (entropy_b - loss[idx].mean(axis=1)) / entropy_b),
            "brier": float(np.mean((p - y) ** 2)),
        }
        if name != reference:
            diff = loss - losses[reference]
            mean, sd = float(diff.mean()), float(diff.std(ddof=1))
            result["gaps"][name] = {
                "reference": reference,
                "mean": mean,
                "sd": sd,
                "ci95": _ci95(diff[idx].mean(axis=1)),
                "games_to_2p5_sigma": (2.5 * sd / abs(mean)) ** 2 if mean else float("inf"),
            }
    return result
