"""winner_loser_split.py — read-only train/holdout feature diagnostic CLI.

Thin CLI wrapper mirroring seasonality_by_week.py's shape: argparse + a
print of scanner.winner_loser's report, nothing else. Answers "which
entry-time signal features separate winners from losers?" for one backtest
run_id — see scanner/winner_loser.py for the analysis logic and
.planning/quick/260819-jjh-add-winner-loser-split-py-diagnostic-cli/ for
the promoted prototype's original run and findings.

Never writes to the database: opens via
scanner.store_db.get_readonly_connection (SQLite `mode=ro` URI).
"""
from __future__ import annotations

import argparse
import sys

from scanner import store_db, winner_loser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Winner/loser feature diagnostic — which entry-time signal "
            "features separate winners from losers, with train/holdout "
            "separation so a finding has to survive data that played no "
            "part in discovering it. Read-only against the database."
        )
    )
    parser.add_argument(
        "--run-id", required=True,
        help="Backtest run_id to analyze",
    )
    parser.add_argument(
        "--split", default="2024-01-01",
        help="Train/holdout boundary date, YYYY-MM-DD (default: 2024-01-01)",
    )
    parser.add_argument(
        "--db", default="data/scanner.db",
        help="Path to the SQLite database (default: data/scanner.db)",
    )
    parser.add_argument(
        "--top", type=int, default=8,
        help="Number of train-best rules to carry to the holdout (default: 8)",
    )
    parser.add_argument(
        "--strategy", choices=["pullback", "breakout"], default=None,
        help="Restrict to one strategy (default: both)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        conn = store_db.get_readonly_connection(args.db)
        try:
            records, missing_columns = winner_loser.load_records(
                conn, args.run_id, strategy=args.strategy
            )
        finally:
            conn.close()
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        train, holdout = winner_loser.split_records(records, args.split)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(
        f"trades: train(<{args.split}) n={len(train)}  "
        f"holdout(>={args.split}) n={len(holdout)}"
    )
    print(f"BASELINE train   mean R = {winner_loser.mean_r(train):+.3f}")
    print(f"BASELINE holdout mean R = {winner_loser.mean_r(holdout):+.3f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
