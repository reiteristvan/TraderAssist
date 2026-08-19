"""Tests for winner_loser_split.py — the thin CLI wrapper."""
from __future__ import annotations

import sqlite3

import winner_loser_split as cli

RUN_ID = "run1"

# Schema-v9 column set (matches the live database — see 260819-jjh-PLAN.md
# <discovered_state>): the four schema-v10 columns (rsi_entry, rvol,
# pullback_depth_pct, pct_to_52w_high) are deliberately ABSENT from this
# fixture's DDL so tests reproduce the real machine, not an idealized one.
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


def _build_v9_fixture_db(tmp_path, rows):
    """Build a throwaway v9-shaped SQLite DB in tmp_path with the given rows.

    Each row is a dict of column->value; unspecified columns default to
    NULL/DEFAULT. Returns the db path. Never touches data/scanner.db.
    """
    db_path = tmp_path / "fixture.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(_V9_SIGNALS_DDL)
    for row in rows:
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        conn.execute(
            f"INSERT INTO signals ({cols}) VALUES ({placeholders})",
            list(row.values()),
        )
    conn.commit()
    conn.close()
    return db_path


def _row(date, ticker, r_multiple, **overrides):
    base = {
        "date": date, "ticker": ticker, "strategy": "pullback", "source": "backtest",
        "run_id": RUN_ID, "score": 50.0, "confidence": "MEDIUM", "atr": 2.0,
        "close": 100.0, "qualified": 1, "r_multiple": r_multiple,
        "target_r": 2.0, "target_atr": 2.5, "industry_momentum": 1.0,
        "industry_above_50ma": 1, "industry_rank_pct": 0.5,
    }
    base.update(overrides)
    return base


def test_tracer_prints_train_holdout_counts_matching_split(tmp_path, capsys):
    rows = [
        _row("2023-06-01", "AAA", 0.5),
        _row("2023-07-01", "BBB", -0.3),
        _row("2023-12-31", "CCC", 1.2),
        _row("2024-01-01", "DDD", -0.5),  # on the boundary -> holdout
        _row("2024-06-01", "EEE", 0.8),
    ]
    db_path = _build_v9_fixture_db(tmp_path, rows)

    result = cli.main(["--run-id", RUN_ID, "--db", str(db_path)])

    captured = capsys.readouterr()
    assert result == 0
    assert "train(<2024-01-01) n=3" in captured.out
    assert "holdout(>=2024-01-01) n=2" in captured.out
