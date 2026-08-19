"""Tests for winner_loser_split.py — the thin CLI wrapper."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import winner_loser_split as cli
from tests._regression_cp1252_winner_loser_helper import (
    RUN_ID as _FULL_RUN_ID,
    _build_fixture_db as _build_full_fixture_db,
)

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


def _build_v9_fixture_db(tmp_path, rows, name="fixture.db"):
    """Build a throwaway v9-shaped SQLite DB in tmp_path with the given rows.

    Each row is a dict of column->value; unspecified columns default to
    NULL/DEFAULT. Returns the db path. Never touches data/scanner.db.
    """
    db_path = tmp_path / name
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


# ── error paths ───────────────────────────────────────────────────────────────

def test_unknown_run_id_exits_2_names_run_id_no_table(tmp_path, capsys):
    rows = [
        _row("2023-06-01", "AAA", 0.5),
        _row("2024-06-01", "EEE", 0.8),
    ]
    db_path = _build_v9_fixture_db(tmp_path, rows)

    result = cli.main(["--run-id", "no-such-run", "--db", str(db_path)])

    captured = capsys.readouterr()
    assert result == 2
    assert "no-such-run" in captured.err
    assert "BASELINE" not in captured.out
    assert captured.out == ""


def test_missing_db_file_exits_2_names_path(tmp_path, capsys):
    missing_path = tmp_path / "does-not-exist.db"

    result = cli.main(["--run-id", RUN_ID, "--db", str(missing_path)])

    captured = capsys.readouterr()
    assert result == 2
    assert str(missing_path) in captured.err
    assert "Traceback" not in captured.err


# ── report content: --top, --strategy, features coverage line ──────────────

def test_full_report_top_flag_prints_n_rule_rows(tmp_path, capsys):
    db_path = tmp_path / "full.db"
    _build_full_fixture_db(db_path)

    result = cli.main(["--run-id", _FULL_RUN_ID, "--db", str(db_path), "--top", "1"])

    captured = capsys.readouterr()
    assert result == 0
    assert "TOP 1 RULES" in captured.out


def test_full_report_features_coverage_line_names_skipped(tmp_path, capsys):
    db_path = tmp_path / "full.db"
    _build_full_fixture_db(db_path)

    result = cli.main(["--run-id", _FULL_RUN_ID, "--db", str(db_path)])

    captured = capsys.readouterr()
    assert result == 0
    # Twelve defined, four skipped as absent columns (schema-v9 fixture).
    assert "12 defined" in captured.out
    assert "4 skipped" in captured.out
    for col in ("rsi_entry", "rvol", "pullback_depth_pct", "pct_to_52w_high"):
        assert col in captured.out
        assert "absent" in captured.out.lower()


def test_strategy_filter_excludes_other_strategy_rows(tmp_path, capsys):
    rows = [
        _row("2023-06-01", "AAA", 0.5, strategy="pullback"),
        _row("2023-07-01", "BBB", -0.3, strategy="breakout"),
        _row("2024-06-01", "EEE", 0.8, strategy="breakout"),
        _row("2024-07-01", "FFF", 0.2, strategy="pullback"),
    ]
    db_path = _build_v9_fixture_db(tmp_path, rows)

    result = cli.main(["--run-id", RUN_ID, "--db", str(db_path), "--strategy", "breakout"])

    captured = capsys.readouterr()
    assert result == 0
    assert "train(<2024-01-01) n=1" in captured.out
    assert "holdout(>=2024-01-01) n=1" in captured.out


# ── read-only guarantee ──────────────────────────────────────────────────────

def test_db_file_bytes_identical_after_successful_run(tmp_path):
    db_path = tmp_path / "full.db"
    _build_full_fixture_db(db_path)
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()

    result = cli.main(["--run-id", _FULL_RUN_ID, "--db", str(db_path)])

    after = hashlib.sha256(db_path.read_bytes()).hexdigest()
    assert result == 0
    assert before == after


# ── cp1252 stream-encoding regression (D-06 / 260712-h7l precedent) ────────

def test_cli_survives_cp1252_stream_encoding_success_path(tmp_path):
    """Regression test for the crash documented in 260712-h7l: every printed
    string must survive a real, non-capsys stream bound to cp1252. capsys
    captures via an in-memory buffer that bypasses real stream encoding
    entirely, which is exactly why that bug shipped unnoticed through 319
    passing tests -- this test exercises the CLI in a subprocess instead."""
    db_path = tmp_path / "cp1252.db"
    helper = Path(__file__).resolve().parent / "_regression_cp1252_winner_loser_helper.py"
    repo_root = Path(__file__).resolve().parent.parent

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    env.pop("PYTHONUTF8", None)

    result = subprocess.run(
        [sys.executable, str(helper), str(db_path), "success"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert "UnicodeEncodeError" not in result.stderr
    assert "UnicodeEncodeError" not in result.stdout


def test_cli_survives_cp1252_stream_encoding_error_path(tmp_path):
    """Same regression, exercised on the unknown-run-id error path (stderr
    write), which is a separate code path from the success-path report."""
    db_path = tmp_path / "cp1252_err.db"
    helper = Path(__file__).resolve().parent / "_regression_cp1252_winner_loser_helper.py"
    repo_root = Path(__file__).resolve().parent.parent

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    env.pop("PYTHONUTF8", None)

    result = subprocess.run(
        [sys.executable, str(helper), str(db_path), "unknown"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "UnicodeEncodeError" not in result.stderr
