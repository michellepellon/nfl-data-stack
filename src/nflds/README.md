# nflds: the field

How much can anyone know about a football game before it is played? The field answers that with
one table and one function:

- **`forecasts`** holds one row per game per forecaster: `game_id, season, week, forecaster, version,
  p_home, kind ('backtest' | 'live'), made_at, data_sha256, code_commit`. `nflds.forecasts.validate`
  rejects `p_home` outside (0, 1), unknown kinds and duplicate `(game_id, forecaster, version, kind)`.
- **`score`** compares forecasters on identical games (only games every forecaster covers) against
  real outcomes, y = 1 / 0 / 0.5 for home win / loss / tie.

## Commands

```
uv run python -m nflds snapshot   # pull nflverse schedules 2015-2025 and pin them (network)
uv run python -m nflds build      # just field-build: write data/forecasts/backtest.parquet
uv run python -m nflds score      # just field-score: print the scoring table and paired gaps
```

`build` takes `--snapshot` and `--out`; `score` takes `--snapshot`, `--forecasts`,
`--seasons START-END` (default 2021-2025) and `--reference` (default `market`).
`data/forecasts/` is generated and gitignored.

## Yards

Log loss is measured in bits: `-(y log2 p + (1 - y) log2(1 - p))`, averaged over games. A forecaster
who always says the home-team base rate `ybar` loses `H` bits per game, the base-rate entropy.
`bits_resolved = H - log_loss`, and

    yards = 100 * bits_resolved / H

So 0 yards is knowing nothing beyond the base rate, 100 yards is knowing every result in advance,
and negative yards is worse than the base rate. The yards interval is a 95% percentile bootstrap
over games (2000 draws, fixed seed). For each forecaster other than the reference, `score` also
reports the paired per-game log-loss gap to the reference (mean, SD, 95% bootstrap interval) and
`games_to_2p5_sigma = (2.5 * sd / |mean|)^2`, the number of games needed to see that gap at 2.5 sigma.
`nflds.score.murphy` gives the reliability / resolution / uncertainty decomposition of Brier.

## Forecasters

Each is a pure function from the snapshot DataFrame to forecast rows (`nflds/forecasters.py`).

- **`market`** (`market-ml-devig-1`): closing moneylines to implied probabilities
  (negative odds `-o / (-o + 100)`, positive `100 / (o + 100)`), devigged as `ph / (ph + pa)`.
  Games missing a moneyline get no forecast.
- **`elo_plain`** (`elo-plain-1`): walk-forward Elo over all game types in
  `(season, gameday, gametime, game_id)` order, using only earlier games.

| Elo parameter | Value |
| --- | --- |
| Starting / mean rating | 1505 |
| Between seasons | each rating moves one third toward 1505 |
| Home field | 48 points, 0 when `location == 'Neutral'` |
| Win probability | `1 / (1 + 10^(-(home - away + hfa) / 400))` |
| K | 20 |
| Margin multiplier | `ln(abs(margin) + 1) * 2.2 / (w * 0.001 + 2.2)`, `w` = rating gap `d` from the winner's side |
| Ties | `y = 0.5`, multiplier `1.0 * 2.2 / (d * 0.001 + 2.2)` so a tie still moves ratings |
| Relocations | OAK -> LV, SD -> LAC, STL -> LA share one rating |

`nflds.forecasters.elo_update` is the canonical single-game Elo update for the project.

## Refreshing the snapshot

`data/snapshots/nflverse_schedules_2015_2025.parquet` and its `.manifest.json` (sha256, row count,
retrieval time, nflreadpy version) are committed. `load_snapshot` refuses to load a parquet whose
sha256 differs from the manifest. To refresh, run `uv run python -m nflds snapshot`, then
`just field-build field-score`, run the tests (the integration windows will flag real changes in
the data) and commit the parquet and manifest together.
