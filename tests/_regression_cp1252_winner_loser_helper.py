"""Standalone subprocess helper for the cp1252 stream-encoding regression test.

Not collected by pytest (leading underscore keeps it outside the
``test_*.py`` discovery pattern). Invoked directly as a subprocess by
``tests/test_winner_loser_cli.py::test_cli_survives_cp1252_stream_encoding``
so winner_loser_split.py's printed report runs through a real, non-capsys
stream bound to cp1252 (see 260712-h7l for why capsys alone would miss this).

Self-contained by precedent (mirrors tests/_regression_cp1252_helper.py):
builds its own tmp fixture database rather than importing from a test
module. The fixture is large enough that at least one feature clears both
the 200-non-null and 150-kept thresholds, so the rule table and rho line
actually render and their characters get exercised by the cp1252 stream.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Insert the repository root (parent of tests/) at the front of sys.path so
# `scanner` and `winner_loser_split` import correctly when this file is run
# directly, outside pytest's `pythonpath` config.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import winner_loser_split as cli

RUN_ID = "cp1252-run"

_V9_SIGNALS_DDL = """
CREATE TABLE signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    strategy    TEXT NOT NULL,
    source      TEXT NOT NULL,
    run_id      TEXT NOT NULL,
    score       REAL,
    confidence  TEXT,
    stop        REAL,
    target      REAL,
    atr         REAL,
    qualified   INTEGER NOT NULL DEFAULT 1,
    failed_gates TEXT,
    close       REAL,
    gate_detail_json TEXT,
    ath_zone    TEXT,
    outcome_checked_at TEXT,
    entry_px    REAL,
    exit_px     REAL,
    exit_reason TEXT,
    r_multiple  REAL,
    holding_days INTEGER,
    flags       TEXT,
    notes       TEXT,
    target_r    REAL,
    target_atr  REAL,
    mae_r       REAL,
    mfe_r       REAL,
    post_stop_reached_target INTEGER,
    post_stop_mfe_r REAL,
    industry_group TEXT,
    industry_momentum REAL,
    industry_above_50ma INTEGER,
    industry_rank_pct REAL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_CONF_CYCLE = ("LOW", "MEDIUM", "HIGH")


def _build_fixture_rows():
    rows = []
    for i in range(260):
        month, day = (i % 12) + 1, (i % 27) + 1
        rows.append((
            f"2020-{month:02d}-{day:02d}", f"T{i}", "pullback", "backtest", RUN_ID,
            float(i), _CONF_CYCLE[i % 3], None, None, 1.0 + (i % 20) * 0.1,
            1, None, 50.0 + i, None, None, None, None, None, None,
            (i % 9) * 0.1 - 0.4, None, None, None,
            float(i * 0.01), float(i * 0.02), None, None, None, None,
            None, float(i % 40), i % 2, float(i % 90),
        ))
    for i in range(60):
        month, day = (i % 12) + 1, (i % 27) + 1
        rows.append((
            f"2024-{month:02d}-{day:02d}", f"H{i}", "pullback", "backtest", RUN_ID,
            float(i * 3), _CONF_CYCLE[i % 3], None, None, 1.0 + (i % 20) * 0.1,
            1, None, 60.0 + i, None, None, None, None, None, None,
            (i % 5) * 0.1, None, None, None,
            float(i * 0.02), float(i * 0.03), None, None, None, None,
            None, float(i % 30), i % 2, float(i % 80),
        ))
    return rows


def _build_fixture_db(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(_V9_SIGNALS_DDL)
    conn.executemany(
        """INSERT INTO signals (
            date, ticker, strategy, source, run_id, score, confidence, stop,
            target, atr, qualified, failed_gates, close, gate_detail_json,
            ath_zone, outcome_checked_at, entry_px, exit_px, exit_reason,
            r_multiple, holding_days, flags, notes, target_r, target_atr,
            mae_r, mfe_r, post_stop_reached_target, post_stop_mfe_r,
            industry_group, industry_momentum, industry_above_50ma,
            industry_rank_pct
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        _build_fixture_rows(),
    )
    conn.commit()
    conn.close()


def main() -> int:
    db_path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "success"

    _build_fixture_db(db_path)

    run_id = RUN_ID if mode == "success" else "no-such-run-id"
    return cli.main(["--run-id", run_id, "--db", db_path])


if __name__ == "__main__":
    sys.exit(main())
