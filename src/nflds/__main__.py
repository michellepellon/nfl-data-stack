# ABOUTME: Command line for the field: `python -m nflds snapshot | build | score`.
# ABOUTME: Pins nflverse data, writes backtest forecast rows and prints the scoring table.
import argparse
import sys
from pathlib import Path

from nflds.forecasts import build_backtest, read_forecasts, write_forecasts
from nflds.score import DEFAULT_SEASONS, score
from nflds.snapshot import REPO_ROOT, SNAPSHOT_PATH, file_sha256, load_snapshot, write_snapshot

FORECASTS_PATH = REPO_ROOT / "data" / "forecasts" / "backtest.parquet"


def season_range(text: str) -> range:
    try:
        start, end = (int(part) for part in text.split("-"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected START-END such as 2021-2025, got '{text}'") from None
    if start > end:
        raise argparse.ArgumentTypeError(f"expected START-END with START <= END, got '{text}'")
    return range(start, end + 1)


def run_snapshot(args) -> None:
    manifest = write_snapshot(args.path)
    print(f"Wrote {manifest['rows']} games to {args.path}")
    print(f"sha256 {manifest['sha256']} (nflreadpy {manifest['nflreadpy_version']})")
    print("Commit the parquet and its manifest together so the pin moves atomically.")


def run_build(args) -> None:
    rows = build_backtest(load_snapshot(args.snapshot), file_sha256(args.snapshot))
    write_forecasts(rows, args.out)
    counts = rows.group_by("forecaster", "version").len().sort("forecaster")
    for forecaster, version, n in counts.iter_rows():
        print(f"{forecaster:<12} {version:<20} {n:>5} games")
    print(f"Wrote {rows.height} backtest forecast rows to {args.out} (code {rows['code_commit'][0]})")


def run_score(args) -> None:
    result = score(
        read_forecasts(args.forecasts), load_snapshot(args.snapshot), seasons=args.seasons, reference=args.reference
    )
    ranked = sorted(result["forecasters"].items(), key=lambda item: -item[1]["yards"])
    entropy = ranked[0][1]["entropy_bits"]
    width = max(len("forecaster"), *(len(name) for name, _ in ranked))
    print(
        f"Seasons {args.seasons[0]}-{args.seasons[-1]}: {result['n']} games forecast by every forecaster, "
        f"base-rate entropy {entropy:.4f} bits"
    )
    print(f"{'forecaster':<{width}}  {'n':>5}  {'logloss_bits':>12}  {'yards':>6}  {'yards_95ci':>14}  {'brier':>6}")
    for name, r in ranked:
        lo, hi = r["yards_ci95"]
        print(
            f"{name:<{width}}  {r['n']:>5}  {r['log_loss_bits']:>12.4f}  {r['yards']:>6.2f}  "
            f"[{lo:>5.2f}, {hi:>5.2f}]  {r['brier']:>6.4f}"
        )
    print(f"\nPaired gap vs {args.reference} (log loss bits per game; positive = worse than {args.reference})")
    for name, _ in ranked:
        if name in result["gaps"]:
            g = result["gaps"][name]
            print(
                f"{name:<{width}}  {g['mean']:+.4f}  sd {g['sd']:.4f}  "
                f"95% CI [{g['ci95'][0]:+.4f}, {g['ci95'][1]:+.4f}]  games to 2.5 sigma: {g['games_to_2p5_sigma']:.0f}"
            )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m nflds",
        description="The field: how much does each forecaster know about an NFL game before it is played?",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="{snapshot,build,score}")

    snap = commands.add_parser(
        "snapshot", help="pull nflverse schedules 2015-2025 and pin them as parquet + sha256 manifest (network)"
    )
    snap.add_argument("--path", type=Path, default=SNAPSHOT_PATH, help="parquet to write (default: %(default)s)")
    snap.set_defaults(run=run_snapshot)

    build = commands.add_parser("build", help="run every forecaster over the pinned snapshot and write backtest rows")
    build.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH, help="pinned parquet (default: %(default)s)")
    build.add_argument("--out", type=Path, default=FORECASTS_PATH, help="forecasts parquet (default: %(default)s)")
    build.set_defaults(run=run_build)

    sc = commands.add_parser("score", help="score forecasters on identical games: log loss bits, yards, Brier, gaps")
    sc.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH, help="pinned parquet (default: %(default)s)")
    sc.add_argument("--forecasts", type=Path, default=FORECASTS_PATH, help="forecasts parquet (default: %(default)s)")
    sc.add_argument(
        "--seasons", type=season_range, default=DEFAULT_SEASONS, metavar="START-END",
        help=f"inclusive season range (default: {DEFAULT_SEASONS[0]}-{DEFAULT_SEASONS[-1]})",
    )
    sc.add_argument("--reference", default="market", help="forecaster the paired gaps compare to (default: market)")
    sc.set_defaults(run=run_score)

    args = parser.parse_args(argv)
    try:
        args.run(args)
    except (FileNotFoundError, ValueError) as error:
        sys.exit(f"error: {error}")


if __name__ == "__main__":
    main()
