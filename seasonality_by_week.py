"""seasonality_by_week.py — Weekly Seasonality Analyzer CLI (Phase 5, SEAS-01/SEAS-02).

Thin CLI wrapper mirroring scan.py's thin-dispatcher convention (D-04): parses
--sector/--universe/--years, delegates to scanner.seasonality.load_sector_dataset,
and prints a Phase-5 data-readiness summary (resolved sector, matched/admitted/
skipped counts). An unknown --sector exits non-zero listing valid GICS sector
names, without running any analysis (SEAS-02).

--output/--bootstrap-iters/--seed are declared here for Phase 6/7 but are not
consumed by any Phase 5 logic.

See .planning/phases/05-sector-resolution-data-input/05-03-PLAN.md.
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
        help="Output path for results (consumed in a later phase; not used yet)",
    )
    parser.add_argument(
        "--bootstrap-iters", type=int, default=None,
        help="Number of bootstrap iterations (consumed in a later phase; not used yet)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for bootstrap reproducibility (consumed in a later phase; not used yet)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        ds = seasonality.load_sector_dataset(args.sector, args.universe, years=args.years)
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
