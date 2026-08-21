"""exit_rule_sweep.py -- read-only exit-rule sweep diagnostic CLI.

Thin CLI wrapper mirroring winner_loser_split.py's shape: argparse + a
print of scanner.exit_sweep's report, nothing else. Answers "does a
different exit rule improve this strategy?" against an existing backtest
run directory -- see scanner/exit_sweep.py for the analysis logic and
.planning/quick/260819-sgn-promote-exit-rule-sweep-tooling-and-docu/ for
the promoted prototypes' original run and findings.

Never opens the database and never runs a backtest: reads only
`<run-dir>/signals.parquet` and the OHLCV price cache via
scanner.exit_sweep.make_bars_provider(). Before any breakeven or target
number is printed, the equivalence gate is checked at every time stop the
selected mode needs; on failure no table is printed at all and the process
exits 3.

ASCII only, whole file, including comments -- see scanner/exit_sweep.py's
module docstring for why.
"""
from __future__ import annotations

import argparse
import sys

from scanner import exit_sweep


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Exit-rule sweep diagnostic -- time-stop / breakeven / "
            "fixed-target variants on an existing backtest signal set, "
            "gated by a trade-by-trade equivalence check against the live "
            "simulator. Read-only: never opens the database, never runs "
            "a backtest."
        )
    )
    parser.add_argument(
        "--run-dir", required=True,
        help="Backtest run directory containing signals.parquet",
    )
    parser.add_argument(
        "--mode", choices=["time", "breakeven", "target", "all"], default="all",
        help="Which sweep(s) to run (default: all)",
    )
    parser.add_argument(
        "--split", default=exit_sweep.DEFAULT_SPLIT,
        help="Train/holdout boundary date, YYYY-MM-DD (default: 2024-01-01)",
    )
    parser.add_argument(
        "--strategy", choices=["pullback", "breakout"], default=None,
        help="Restrict to one strategy (default: both)",
    )
    return parser


def _gate_time_stops(mode: str) -> tuple:
    if mode == "time":
        return (exit_sweep.ANCHOR_TIME_STOP,)
    if mode == "breakeven":
        return exit_sweep.BE_TIME_STOPS
    if mode == "target":
        return exit_sweep.TARGET_TIME_STOPS
    return exit_sweep.REPLICA_TIME_STOPS


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        exit_sweep.validate_split(args.split)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        signals = exit_sweep.load_signals(args.run_dir, strategy=args.strategy)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    bars_provider = exit_sweep.make_bars_provider()

    gate_time_stops = _gate_time_stops(args.mode)
    reports = [
        exit_sweep.check_equivalence(signals, bars_provider, time_stop=ts)
        for ts in gate_time_stops
    ]

    header = exit_sweep.render_header(args.run_dir, args.split, args.strategy, len(signals))
    gate_section = exit_sweep.render_gate_section(reports)

    if not all(r.ok for r in reports):
        print(header, file=sys.stderr)
        print(gate_section, file=sys.stderr)
        return 3

    sections = [header, gate_section]

    if args.mode == "time":
        time_rows = exit_sweep.sweep_time(signals, bars_provider, split=args.split)
        sections.append(exit_sweep.render_time_table(time_rows))
    else:
        sections.append("not implemented yet")

    print("\n\n".join(sections))
    return 0


if __name__ == "__main__":
    sys.exit(main())
