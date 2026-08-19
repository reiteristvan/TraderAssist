"""Tests for scanner.store_db — E9.1.

Acceptance criteria:
1. migrate() idempotent; schema_version row present.
2. All SQL string literals live in store_db.py (grep — not tested here).
3. Round-trip: write a Signal, read it back unchanged.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from scanner import store_db


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    """In-memory DB at a temp path; migrated once."""
    path = tmp_path / "test.db"
    store_db.migrate(db_path=path)
    conn = store_db.get_connection(path)
    yield conn
    conn.close()


def _sample_signal(
    ticker="AAPL",
    sig_date="2026-01-05",
    strategy="pullback",
    source="live",
    run_id="2026-01-05",
) -> dict:
    return {
        "date": sig_date,
        "ticker": ticker,
        "strategy": strategy,
        "source": source,
        "run_id": run_id,
        "score": 65.0,
        "confidence": "MEDIUM",
        "stop": 90.0,
        "target": 110.0,
        "atr": 1.5,
        "qualified": 1,
        "failed_gates": "",
        "close": 100.0,
    }


def _sample_run(run_id="bt_2026") -> dict:
    return {
        "run_id": run_id,
        "kind": "backtest",
        "strategy": "pullback",
        "universe": "500",
        "params_json": json.dumps({"start": "2023-01-01"}),
        "started_at": "2026-06-22T10:00:00",
        "finished_at": "2026-06-22T10:30:00",
        "signal_count": 42,
    }


# ── E9.1 AC1 — migrate() is idempotent ───────────────────────────────────────

def test_migrate_idempotent(tmp_path):
    path = tmp_path / "test.db"
    store_db.migrate(db_path=path)
    store_db.migrate(db_path=path)  # second call must not raise
    store_db.migrate(db_path=path)  # third call too
    conn = store_db.get_connection(path)
    ver = store_db.get_schema_version(conn)
    conn.close()
    assert ver == 10


def test_migrate_schema_version_present(db):
    assert store_db.get_schema_version(db) == 10


# ── E9.1 AC3 — round-trip signal ─────────────────────────────────────────────

def test_signal_round_trip(db):
    sig = _sample_signal()
    store_db.insert_signal(db, sig)

    row = db.execute(
        "SELECT * FROM signals WHERE ticker = 'AAPL' AND date = '2026-01-05'"
    ).fetchone()
    assert row is not None
    assert row["ticker"] == "AAPL"
    assert float(row["score"]) == pytest.approx(65.0)
    assert float(row["stop"]) == pytest.approx(90.0)
    assert float(row["target"]) == pytest.approx(110.0)
    assert row["confidence"] == "MEDIUM"
    assert row["source"] == "live"
    assert row["qualified"] == 1


def test_insert_or_ignore_no_duplicate(db):
    """INSERT OR IGNORE: same unique key does not raise or duplicate."""
    sig = _sample_signal()
    store_db.insert_signal(db, sig)
    store_db.insert_signal(db, sig)  # second insert must be silently ignored
    count = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    assert count == 1


def test_unique_key_different_run_id(db):
    """Different run_id → different rows (same date/ticker/strategy/source)."""
    sig1 = _sample_signal(run_id="2026-01-05")
    sig2 = _sample_signal(run_id="2026-01-06")
    store_db.insert_signal(db, sig1)
    store_db.insert_signal(db, sig2)
    count = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    assert count == 2


# ── unresolved / outcome update ───────────────────────────────────────────────

def test_get_unresolved_live_signals(db):
    store_db.insert_signal(db, _sample_signal())
    rows = store_db.get_unresolved_live_signals(db)
    assert len(rows) == 1
    assert rows[0]["exit_reason"] is None


def test_update_signal_outcome(db):
    store_db.insert_signal(db, _sample_signal())
    row = db.execute("SELECT id FROM signals").fetchone()
    outcome = {
        "outcome_checked_at": "2026-01-16T12:00:00",
        "entry_px": 101.0,
        "exit_px": 110.0,
        "exit_reason": "target",
        "r_multiple": 0.9,
        "holding_days": 7,
        "flags": json.dumps({}),
    }
    store_db.update_signal_outcome(db, row["id"], outcome)

    updated = db.execute("SELECT * FROM signals WHERE id = ?", (row["id"],)).fetchone()
    assert updated["exit_reason"] == "target"
    assert float(updated["r_multiple"]) == pytest.approx(0.9)
    assert updated["holding_days"] == 7


def test_resolved_signal_not_in_unresolved(db):
    store_db.insert_signal(db, _sample_signal())
    row = db.execute("SELECT id FROM signals").fetchone()
    store_db.update_signal_outcome(db, row["id"], {
        "outcome_checked_at": "2026-01-16",
        "entry_px": 100.0, "exit_px": 110.0,
        "exit_reason": "target", "r_multiple": 1.0,
        "holding_days": 10, "flags": "{}",
    })
    unresolved = store_db.get_unresolved_live_signals(db)
    assert len(unresolved) == 0


# ── runs ──────────────────────────────────────────────────────────────────────

def test_insert_run(db):
    store_db.insert_run(db, _sample_run())
    runs = store_db.get_backtest_runs(db)
    assert len(runs) == 1
    assert runs[0]["run_id"] == "bt_2026"
    assert runs[0]["kind"] == "backtest"


def test_insert_run_ignore_duplicate(db):
    store_db.insert_run(db, _sample_run())
    store_db.insert_run(db, _sample_run())  # duplicate run_id
    runs = store_db.get_backtest_runs(db)
    assert len(runs) == 1


# ── backtest_reports ──────────────────────────────────────────────────────────

def test_insert_and_get_backtest_report(db):
    store_db.insert_run(db, _sample_run("bt_001"))
    metrics = {"count": 10, "win_rate": 0.5, "expectancy_r": 0.3}
    biases = ["survivorship", "look-ahead"]
    store_db.insert_backtest_report(db, "bt_001", metrics, biases)

    report = store_db.get_run_report(db, "bt_001")
    assert report is not None
    assert report["metrics"]["count"] == 10
    assert report["metrics"]["win_rate"] == pytest.approx(0.5)
    assert "survivorship" in report["biases"]


def test_get_run_report_missing(db):
    assert store_db.get_run_report(db, "nonexistent") is None


# ── E12.2a — gate_detail_json round-trip ─────────────────────────────────────

def test_gate_detail_round_trip(db):
    """gate_detail_json stored and readable as a JSON string."""
    gate_detail = [
        {"name": "Trend alignment", "status": "pass", "detail": "close > SMA50 > SMA200"},
        {"name": "Earnings clear", "status": "skip", "detail": "no earnings data"},
        {"name": "Profitable", "status": "fail", "detail": ""},
    ]
    sig = _sample_signal()
    sig["gate_detail_json"] = json.dumps(gate_detail)
    store_db.insert_signal(db, sig)

    row = db.execute("SELECT gate_detail_json FROM signals WHERE ticker='AAPL'").fetchone()
    assert row is not None
    parsed = json.loads(row["gate_detail_json"])
    assert len(parsed) == 3
    assert parsed[0]["name"] == "Trend alignment"
    assert parsed[1]["status"] == "skip"
    assert parsed[2]["status"] == "fail"


def test_gate_detail_defaults_null(db):
    """Signals inserted without gate_detail_json have NULL (not an error)."""
    sig = _sample_signal()  # no gate_detail_json key
    store_db.insert_signal(db, sig)
    row = db.execute("SELECT gate_detail_json FROM signals WHERE ticker='AAPL'").fetchone()
    assert row["gate_detail_json"] is None


def test_migrate_v1_to_current(tmp_path):
    """Existing v1 DB upgrades through all versions to the current schema."""
    import sqlite3 as _sqlite3
    path = tmp_path / "v1.db"
    # Build a v1 DB manually (no gate_detail_json column)
    conn = _sqlite3.connect(str(path))
    conn.execute("""CREATE TABLE schema_version (version INTEGER NOT NULL)""")
    conn.execute("""CREATE TABLE signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, ticker TEXT NOT NULL, strategy TEXT NOT NULL,
        source TEXT NOT NULL, run_id TEXT NOT NULL,
        score REAL, confidence TEXT, stop REAL, target REAL, atr REAL,
        qualified INTEGER NOT NULL DEFAULT 1, failed_gates TEXT, close REAL,
        outcome_checked_at TEXT, entry_px REAL, exit_px REAL,
        exit_reason TEXT, r_multiple REAL, holding_days INTEGER, flags TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (date, ticker, strategy, source, run_id)
    )""")
    conn.execute("INSERT INTO schema_version VALUES (1)")
    conn.commit()
    conn.close()

    # migrate() should upgrade to current version
    store_db.migrate(db_path=path)
    conn2 = store_db.get_connection(path)
    assert store_db.get_schema_version(conn2) == 10
    # Columns added in v2/v3 must exist
    cols = [r[1] for r in conn2.execute("PRAGMA table_info(signals)").fetchall()]
    assert "gate_detail_json" in cols
    assert "ath_zone" in cols
    # notes column added in v6 must exist
    assert "notes" in cols
    # target_r/target_atr added in v7 must exist
    assert "target_r" in cols
    assert "target_atr" in cols
    # mae_r/mfe_r/post_stop_* added in v8 must exist
    assert "mae_r" in cols
    assert "mfe_r" in cols
    assert "post_stop_reached_target" in cols
    assert "post_stop_mfe_r" in cols
    # industry_* added in v9 must exist
    assert "industry_group" in cols
    assert "industry_momentum" in cols
    assert "industry_above_50ma" in cols
    assert "industry_rank_pct" in cols
    # rsi_entry/rvol/pullback_depth_pct/pct_to_52w_high added in v10 must exist
    assert "rsi_entry" in cols
    assert "rvol" in cols
    assert "pullback_depth_pct" in cols
    assert "pct_to_52w_high" in cols
    # bars table added in v5 must exist
    tables = [r[0] for r in conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "bars" in tables
    conn2.close()


# ── E12.7 — bars round-trip ───────────────────────────────────────────────────

def _sample_bars(ticker: str = "AAPL", n: int = 5) -> list[dict]:
    return [
        {
            "ticker": ticker,
            "date": f"2026-01-{i + 1:02d}",
            "open": 100.0 + i,
            "high": 102.0 + i,
            "low": 99.0 + i,
            "close": 101.0 + i,
            "volume": 1_000_000.0 * (i + 1),
        }
        for i in range(n)
    ]


def test_upsert_bars_round_trip(db):
    bars = _sample_bars("AAPL", 5)
    store_db.upsert_bars(db, "AAPL", bars)
    result = store_db.get_ohlcv(db, "AAPL", limit=10)
    assert len(result) == 5
    assert result[0]["date"] == "2026-01-01"
    assert result[-1]["date"] == "2026-01-05"
    assert result[0]["open"] == pytest.approx(100.0)
    assert result[0]["volume"] == pytest.approx(1_000_000.0)


def test_upsert_bars_replace(db):
    """INSERT OR REPLACE: re-inserting same (ticker, date) updates the row."""
    bars = _sample_bars("AAPL", 1)
    store_db.upsert_bars(db, "AAPL", bars)
    bars[0]["close"] = 999.0
    store_db.upsert_bars(db, "AAPL", bars)
    result = store_db.get_ohlcv(db, "AAPL")
    assert len(result) == 1
    assert result[0]["close"] == pytest.approx(999.0)


def test_get_ohlcv_limit(db):
    bars = _sample_bars("AAPL", 10)
    store_db.upsert_bars(db, "AAPL", bars)
    result = store_db.get_ohlcv(db, "AAPL", limit=3)
    assert len(result) == 3
    # limit=3 returns the 3 most recent bars, in chronological order
    assert result[-1]["date"] == "2026-01-10"


def test_get_ohlcv_empty(db):
    result = store_db.get_ohlcv(db, "UNKNOWN")
    assert result == []


def test_upsert_bars_case_insensitive(db):
    bars = _sample_bars("aapl", 2)  # lowercase ticker
    store_db.upsert_bars(db, "aapl", bars)
    result = store_db.get_ohlcv(db, "AAPL")  # uppercase lookup
    assert len(result) == 2


# ── batch insert ──────────────────────────────────────────────────────────────

def test_insert_signals_batch(db):
    sigs = [_sample_signal(ticker="A"), _sample_signal(ticker="B")]
    n = store_db.insert_signals_batch(db, sigs)
    assert n == 2
    count = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    assert count == 2


def test_insert_signals_batch_ignore_dups(db):
    sigs = [_sample_signal(ticker="A")] * 3  # same unique key 3×
    n = store_db.insert_signals_batch(db, sigs)
    assert n == 1  # only first inserted


# ── E13.1 — target_r / target_atr round-trip ─────────────────────────────────

def test_target_r_atr_round_trip(db):
    """target_r and target_atr written and read back via update_signal_outcome."""
    store_db.insert_signal(db, _sample_signal())
    row = db.execute("SELECT id FROM signals").fetchone()
    outcome = {
        "outcome_checked_at": "2026-06-26T12:00:00",
        "entry_px": 100.0,
        "exit_px": 110.0,
        "exit_reason": "target",
        "r_multiple": 1.0,
        "holding_days": 5,
        "flags": json.dumps({}),
        "target_r": 2.5,
        "target_atr": 6.67,
    }
    store_db.update_signal_outcome(db, row["id"], outcome)

    updated = db.execute("SELECT * FROM signals WHERE id = ?", (row["id"],)).fetchone()
    assert float(updated["target_r"])   == pytest.approx(2.5)
    assert float(updated["target_atr"]) == pytest.approx(6.67)


def test_mae_mfe_round_trip(db):
    """mae_r, mfe_r, post_stop_reached_target, post_stop_mfe_r persisted and readable."""
    store_db.insert_signal(db, _sample_signal(ticker="MAE"))
    row = db.execute("SELECT id FROM signals WHERE ticker='MAE'").fetchone()
    outcome = {
        "outcome_checked_at": "2026-06-26T12:00:00",
        "entry_px": 100.0,
        "exit_px": 90.0,
        "exit_reason": "stop",
        "r_multiple": -1.0,
        "holding_days": 3,
        "flags": json.dumps({}),
        "target_r": 2.0,
        "target_atr": 5.0,
        "mae_r": -1.1,
        "mfe_r": 0.3,
        "post_stop_reached_target": 1,
        "post_stop_mfe_r": 1.5,
    }
    store_db.update_signal_outcome(db, row["id"], outcome)

    updated = db.execute("SELECT * FROM signals WHERE ticker='MAE'").fetchone()
    assert float(updated["mae_r"])             == pytest.approx(-1.1)
    assert float(updated["mfe_r"])             == pytest.approx(0.3)
    assert updated["post_stop_reached_target"] == 1
    assert float(updated["post_stop_mfe_r"])   == pytest.approx(1.5)


def test_mae_mfe_default_null(db):
    """update_signal_outcome without mae/mfe fields writes NULL."""
    store_db.insert_signal(db, _sample_signal(ticker="NULL"))
    row = db.execute("SELECT id FROM signals WHERE ticker='NULL'").fetchone()
    store_db.update_signal_outcome(db, row["id"], {
        "outcome_checked_at": "2026-06-26",
        "entry_px": 100.0, "exit_px": 110.0,
        "exit_reason": "target", "r_multiple": 1.0,
        "holding_days": 5, "flags": "{}",
    })
    updated = db.execute("SELECT * FROM signals WHERE ticker='NULL'").fetchone()
    assert updated["mae_r"]                    is None
    assert updated["mfe_r"]                    is None
    assert updated["post_stop_reached_target"] is None
    assert updated["post_stop_mfe_r"]          is None


def test_target_r_defaults_null(db):
    """update_signal_outcome without target_r/target_atr writes NULL."""
    store_db.insert_signal(db, _sample_signal())
    row = db.execute("SELECT id FROM signals").fetchone()
    store_db.update_signal_outcome(db, row["id"], {
        "outcome_checked_at": "2026-06-26",
        "entry_px": 100.0, "exit_px": 110.0,
        "exit_reason": "target", "r_multiple": 1.0,
        "holding_days": 5, "flags": "{}",
    })
    updated = db.execute("SELECT * FROM signals WHERE id = ?", (row["id"],)).fetchone()
    assert updated["target_r"]   is None
    assert updated["target_atr"] is None


# ── Phase 2 — industry momentum NULL round-trip ───────────────────────────────

def test_industry_momentum_null_round_trip(db):
    """industry_momentum=None must be stored as SQL NULL, not 0.0 (anti-NaN pitfall)."""
    sig = {
        **_sample_signal(),
        "industry_group": None,
        "industry_momentum": None,
        "industry_above_50ma": None,
        "industry_rank_pct": None,
    }
    store_db.insert_signal(db, sig)
    row = db.execute("SELECT * FROM signals WHERE ticker = 'AAPL'").fetchone()
    assert row["industry_momentum"] is None
    assert row["industry_group"] is None
    assert row["industry_rank_pct"] is None


# ── Quick task 260819-gv9 — v10 entry-time feature columns ────────────────────

_ENTRY_COLS = ("rsi_entry", "rvol", "pullback_depth_pct", "pct_to_52w_high")


def test_schema_version_10_after_migrate(tmp_path):
    """schema_version reads 10 after migrate() on a fresh DB (D-02)."""
    path = tmp_path / "v10.db"
    store_db.migrate(db_path=path)
    conn = store_db.get_connection(path)
    assert store_db.get_schema_version(conn) == 10
    conn.close()


def test_signals_table_has_v10_columns(db):
    """PRAGMA table_info(signals) reports all four new REAL columns."""
    cols = {r[1] for r in db.execute("PRAGMA table_info(signals)").fetchall()}
    assert {"rsi_entry", "rvol", "pullback_depth_pct", "pct_to_52w_high"} <= cols


def test_insert_signal_round_trips_entry_features(db):
    """insert_signal() with the four keys present round-trips all four values unchanged.

    Asserted independently of insert_signals_batch — a regression in either
    function must fail on its own (T-gv9-03).
    """
    sig = {
        **_sample_signal(ticker="ENTRY1"),
        "rsi_entry": 48.0,
        "rvol": 1.5,
        "pullback_depth_pct": 5.17,
        "pct_to_52w_high": 20.0,
    }
    store_db.insert_signal(db, sig)
    row = db.execute("SELECT * FROM signals WHERE ticker = 'ENTRY1'").fetchone()
    assert float(row["rsi_entry"]) == pytest.approx(48.0)
    assert float(row["rvol"]) == pytest.approx(1.5)
    assert float(row["pullback_depth_pct"]) == pytest.approx(5.17)
    assert float(row["pct_to_52w_high"]) == pytest.approx(20.0)


def test_insert_signals_batch_round_trips_entry_features(db):
    """insert_signals_batch() with the four keys present round-trips all four values
    unchanged — asserted independently of insert_signal (T-gv9-03)."""
    sigs = [{
        **_sample_signal(ticker="ENTRY2"),
        "rsi_entry": 61.0,
        "rvol": 3.48,
        "pullback_depth_pct": None,
        "pct_to_52w_high": 0.49,
    }]
    n = store_db.insert_signals_batch(db, sigs)
    assert n == 1
    row = db.execute("SELECT * FROM signals WHERE ticker = 'ENTRY2'").fetchone()
    assert float(row["rsi_entry"]) == pytest.approx(61.0)
    assert float(row["rvol"]) == pytest.approx(3.48)
    assert row["pullback_depth_pct"] is None
    assert float(row["pct_to_52w_high"]) == pytest.approx(0.49)


def test_insert_signal_omitting_entry_features_yields_null(db):
    """A signal dict that omits all four keys still inserts and yields NULL columns
    (the _sample_signal compatibility contract — prior_investigation 8)."""
    store_db.insert_signal(db, _sample_signal(ticker="ENTRY3"))
    row = db.execute("SELECT * FROM signals WHERE ticker = 'ENTRY3'").fetchone()
    for col in _ENTRY_COLS:
        assert row[col] is None


def test_insert_signals_batch_omitting_entry_features_yields_null(db):
    """Same omit-keys contract for the batch insert path."""
    n = store_db.insert_signals_batch(db, [_sample_signal(ticker="ENTRY4")])
    assert n == 1
    row = db.execute("SELECT * FROM signals WHERE ticker = 'ENTRY4'").fetchone()
    for col in _ENTRY_COLS:
        assert row[col] is None


def test_migrate_v9_to_v10_idempotent_preserves_existing_row(tmp_path):
    """Simulated upgrade: hand-build a v9 signals table (no v10 columns), run
    migrate() TWICE, and assert no error, version 10, the four columns present,
    and the pre-existing row's other columns unchanged with the four new ones NULL."""
    import sqlite3 as _sqlite3
    path = tmp_path / "v9.db"
    conn = _sqlite3.connect(str(path))
    conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    conn.execute("""CREATE TABLE signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, ticker TEXT NOT NULL, strategy TEXT NOT NULL,
        source TEXT NOT NULL, run_id TEXT NOT NULL,
        score REAL, confidence TEXT, stop REAL, target REAL, atr REAL,
        qualified INTEGER NOT NULL DEFAULT 1, failed_gates TEXT, close REAL,
        gate_detail_json TEXT, ath_zone TEXT,
        outcome_checked_at TEXT, entry_px REAL, exit_px REAL,
        exit_reason TEXT, r_multiple REAL, holding_days INTEGER, flags TEXT,
        notes TEXT, target_r REAL, target_atr REAL,
        mae_r REAL, mfe_r REAL, post_stop_reached_target INTEGER, post_stop_mfe_r REAL,
        industry_group TEXT, industry_momentum REAL, industry_above_50ma INTEGER,
        industry_rank_pct REAL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (date, ticker, strategy, source, run_id)
    )""")
    conn.execute("INSERT INTO schema_version VALUES (9)")
    conn.execute(
        """INSERT INTO signals (date, ticker, strategy, source, run_id, score, close)
           VALUES ('2026-01-05', 'PRE', 'pullback', 'live', '2026-01-05', 55.0, 100.0)"""
    )
    conn.commit()
    conn.close()

    store_db.migrate(db_path=path)
    store_db.migrate(db_path=path)  # idempotent — second run must not raise/duplicate

    conn2 = store_db.get_connection(path)
    assert store_db.get_schema_version(conn2) == 10
    cols = {r[1] for r in conn2.execute("PRAGMA table_info(signals)").fetchall()}
    assert {"rsi_entry", "rvol", "pullback_depth_pct", "pct_to_52w_high"} <= cols

    row = conn2.execute("SELECT * FROM signals WHERE ticker = 'PRE'").fetchone()
    assert row is not None
    assert float(row["score"]) == pytest.approx(55.0)
    assert float(row["close"]) == pytest.approx(100.0)
    for col in _ENTRY_COLS:
        assert row[col] is None

    count = conn2.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    assert count == 1
    conn2.close()
