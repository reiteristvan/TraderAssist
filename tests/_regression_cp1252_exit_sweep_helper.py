"""Standalone subprocess helper for the cp1252 stream-encoding regression test.

Not collected by pytest (leading underscore keeps it outside the
``test_*.py`` discovery pattern). Invoked directly as a subprocess by
``tests/test_exit_rule_sweep_cli.py`` so exit_rule_sweep.py's printed report
runs through a real, non-capsys stream bound to cp1252 (see 260712-h7l for
why capsys alone would miss this).

Self-contained by precedent (mirrors
tests/_regression_cp1252_winner_loser_helper.py): builds its own fixture
run directory and synthetic price bars rather than importing from a test
module, and substitutes the bars-provider factory so nothing here touches
the real price cache.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Insert the repository root (parent of tests/) at the front of sys.path so
# `scanner` and `exit_rule_sweep` import correctly when this file is run
# directly, outside pytest's `pythonpath` config.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import exit_rule_sweep as cli
from scanner import exit_sweep

RUN_DIR_NAME = "cp1252_fixture_run"


def _bars(rows, start="2020-01-02"):
    idx = pd.bdate_range(start=start, periods=len(rows))
    return pd.DataFrame(
        {
            "Open": [r[0] for r in rows],
            "High": [r[1] for r in rows],
            "Low": [r[2] for r in rows],
            "Close": [r[3] for r in rows],
            "Volume": [1000] * len(rows),
        },
        index=idx,
    )


def _build_fixture(work_dir: Path):
    """Write a small signals.parquet under work_dir/RUN_DIR_NAME and return
    a dict-backed bars mapping large enough to clear every configured time
    stop for both breakeven and target sweeps, so --mode all's full report
    (all three tables plus the gate line) actually renders and every
    character in it gets exercised by the cp1252 stream."""
    run_dir = work_dir / RUN_DIR_NAME
    run_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    bars_map: dict[str, pd.DataFrame] = {}
    for i in range(60):
        ticker = f"T{i}"
        month, day = (i % 12) + 1, (i % 27) + 1
        rows.append({
            "date": f"2020-{month:02d}-{day:02d}",
            "ticker": ticker,
            "strategy": "pullback",
            "score": float(i),
            "confidence": "MEDIUM",
            "stop": 90.0,
            "target": 120.0,
            "atr": 2.0,
            "qualified": True,
            "close": 100.0,
        })
        # 45 bars: enough for BE_TIME_STOPS's max (40) and TARGET_TIME_STOPS.
        # Every bar stays inside (90, 120) so nothing hits stop or target --
        # every trade resolves via the time-stop close, exercising the
        # "ran out of the window" path uniformly.
        bar_rows = [(100.0, 105.0 + (i % 3), 96.0, 101.0)] * 45
        bars_map[ticker] = _bars(bar_rows)

    pd.DataFrame(rows).to_parquet(run_dir / "signals.parquet")
    return run_dir, bars_map


def main() -> int:
    work_dir = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "success"

    if mode == "success":
        run_dir, bars_map = _build_fixture(work_dir)
        exit_sweep.make_bars_provider = lambda: (lambda ticker: bars_map.get(ticker))
        return cli.main(["--run-dir", str(run_dir), "--mode", "all"])
    else:
        missing_dir = work_dir / "does-not-exist-fixture"
        return cli.main(["--run-dir", str(missing_dir), "--mode", "all"])


if __name__ == "__main__":
    sys.exit(main())
