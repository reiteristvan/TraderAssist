"""seasonality_by_week.py — Weekly Seasonality Analyzer CLI (Phase 5, SEAS-01/SEAS-02).

Thin CLI wrapper mirroring scan.py's thin-dispatcher convention (D-04): parses
--sector/--universe/--years, delegates to scanner.seasonality.load_sector_dataset,
and prints a Phase-5 data-readiness summary (resolved sector, matched/admitted/
skipped counts). An unknown --sector exits non-zero listing valid GICS sector
names, without running any analysis (SEAS-02).

Phase 6 (SEAS-08) wires --bootstrap-iters/--seed through to
scanner.seasonality.compute_seasonality_stats.

Phase 7 (SEAS-10..13) prints the survivorship-bias warning header, the
52-row per-week table, and the interpretive summary on every run, and
additionally writes the padded table to CSV when --output is given
(stdout always happens regardless of --output, D-14).

See .planning/phases/05-sector-resolution-data-input/05-03-PLAN.md,
.planning/phases/06-seasonality-statistics-verification/06-03-PLAN.md, and
.planning/phases/07-cli-output-reporting/07-02-PLAN.md.
"""
from __future__ import annotations

import argparse
import logging
import sys

from scanner import seasonality


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Weekly Seasonality Analyzer — test whether stocks in a sector show "
            "statistically significant calendar-week seasonality."
        )
    )
    parser.add_argument(
        "--sector", required=True,
        help="GICS sector name (case-insensitive), e.g. Technology",
    )
    parser.add_argument(
        "--universe", default="sp500",
        help="Universe to scan: sp400, sp500, sp600, or all (default: sp500)",
    )
    parser.add_argument(
        "--years", type=int, default=None,
        help="Trim admitted history to the most recent N years (default: full validated history)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Write the padded 52-row results table to this CSV path (additive -- "
        "stdout output always prints regardless of --output)",
    )
    parser.add_argument(
        "--bootstrap-iters", type=int, default=None,
        help="Number of bootstrap iterations for the year-block CI (default: 1000)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for bootstrap reproducibility (default: 42)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        ds = seasonality.load_sector_dataset(args.sector, args.universe, years=args.years)
        result = seasonality.compute_seasonality_stats(
            ds, bootstrap_iters=args.bootstrap_iters, seed=args.seed
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"Sector: {ds.sector}  Universe: {ds.universe}")
    print(f"Admitted: {len(ds.frames)}  Skipped: {len(ds.skipped)}")
    if ds.skipped:
        preview = ds.skipped[:10]
        print(f"Skipped tickers (showing {len(preview)} of {len(ds.skipped)}):")
        for ticker, reason in preview:
            print(f"  {ticker}: {reason}")

    print(
        f"Bootstrap iters: {result.bootstrap_iters}  Seed: {result.seed}  "
        f"Years: {result.n_years}"
    )
    print()
    print(seasonality._SURVIVORSHIP_WARNING)
    print()

    padded = seasonality.pad_weeks_table(result)
    print(seasonality.render_weeks_table(padded))
    print()
    print(seasonality.build_summary(result))

    if args.output:
        seasonality.write_weeks_csv(padded, args.output)
        print(f"\nSaved → {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
