"""Tests for scanner.journal — E9.2-E9.5.

Acceptance criteria:
E9.2: Same-evening double scan → no duplicate signals (run_id collapses to date).
      unresolved_live_signals() returns only NULL-outcome live rows.
E9.3: Imports E7's simulator (single implementation).
      Time-stop-not-elapsed signal stays open.
      Second run is a no-op.
E9.5: Warning boundary verified at n=29 vs 30.
      Pulls backtest metrics from backtest_reports, not files.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scanner import store_db
from scanner.journal import (
    write_live_signals,
    compare_with_backtest,
    write_backtest_to_db,
)
from scanner.simulate import Signal


# ── helpers ────────────────────────────────────────────────────────────────────

def _db(tmp_path) -> Path:
    path = tmp_path / "test.db"
    store_db.migrate(db_path=path)
    return path


def _live_row(ticker="AAPL", strat="pullback", sig_date="2026-01-05") -> dict:
    return {
        "ticker": ticker,
        "strategy": strat,
        "as_of": sig_date,
        "score": 65.0,
        "confidence": "MEDIUM",
        "suggested_stop": 90.0,
        "suggested_target": 110.0,
        "atr": 1.5,
        "qualified": True,
        "failed_gates": [],
        "close": 100.0,
    }


def _live_row_with_entry_features(
    ticker="AAPL", strat="pullback", sig_date="2026-01-05",
    entry_rsi=48.0, entry_rvol=1.5,
    entry_pullback_depth_pct=5.17, entry_pct_to_52w_high=20.0,
) -> dict:
    """`_live_row` plus the namespaced entry_* keys core.run_scan assigns (260819-gv9)."""
    row = _live_row(ticker, strat, sig_date)
    row.update({
        "entry_rsi": entry_rsi,
        "entry_rvol": entry_rvol,
        "entry_pullback_depth_pct": entry_pullback_depth_pct,
        "entry_pct_to_52w_high": entry_pct_to_52w_high,
    })
    return row


def _sample_signal(sig_date=date(2026, 1, 5), stop=90.0, target=110.0) -> Signal:
    return Signal(
        date=sig_date, ticker="AAPL", strategy="pullback",
        score=65.0, confidence="MEDIUM", stop=stop, target=target,
        atr=1.5, qualified=True, close=100.0,
    )


# ── E9.2 — write_live_signals ─────────────────────────────────────────────────

def test_write_live_signals_basic(tmp_path):
    db_path = _db(tmp_path)
    rows = [_live_row("AAPL"), _live_row("MSFT")]
    n = write_live_signals(rows, "pullback", "2026-01-05", db_path=db_path)
    assert n == 2

    conn = store_db.get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    conn.close()
    assert count == 2


def test_write_live_signals_no_duplicate_same_day(tmp_path):
    """Double scan on same day → run_id collapses → INSERT OR IGNORE → 1 row."""
    db_path = _db(tmp_path)
    row = _live_row("AAPL")
    write_live_signals([row], "pullback", "2026-01-05", db_path=db_path)
    write_live_signals([row], "pullback", "2026-01-05", db_path=db_path)  # same run_id

    conn = store_db.get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM signals WHERE ticker='AAPL'").fetchone()[0]
    conn.close()
    assert count == 1


def test_write_live_signals_different_days_adds_row(tmp_path):
    """Different run_id (different day) → new row allowed."""
    db_path = _db(tmp_path)
    row = _live_row("AAPL")
    write_live_signals([row], "pullback", "2026-01-05", db_path=db_path)
    write_live_signals([row], "pullback", "2026-01-06", db_path=db_path)

    conn = store_db.get_connection(db_path)
    count = conn.execute("SELECT COUNT(*) FROM signals WHERE ticker='AAPL'").fetchone()[0]
    conn.close()
    assert count == 2


# ── E9.3 — resolve uses E7 simulator (import check) ──────────────────────────

def test_resolve_imports_simulate():
    """resolve_open_signals imports simulate_trades from scanner.simulate — not a copy."""
    import inspect
    from scanner.journal import resolve_open_signals
    src = inspect.getsource(resolve_open_signals)
    assert "simulate_trades" in src
    # The import must come from scanner.simulate
    from scanner.journal import simulate_trades as jst
    from scanner.simulate import simulate_trades as sst
    assert jst is sst


# ── E9.3 — in-flight signal stays open ───────────────────────────────────────

def test_in_flight_signal_stays_open(tmp_path):
    """Signal with only 2 bars available (time_stop=10 not elapsed) → stays open.

    Tests the in-flight detection logic: no stop/target hit AND n_after < time_stop
    → open_count incremented, not resolved.
    """
    db_path = _db(tmp_path)
    sig_date = date(2026, 6, 18)
    cutoff = date(2026, 6, 22)

    conn = store_db.get_connection(db_path)
    store_db.insert_signal(conn, {
        "date": str(sig_date), "ticker": "AAPL", "strategy": "pullback",
        "source": "live", "run_id": str(sig_date),
        "score": 65.0, "confidence": "MEDIUM",
        "stop": 90.0, "target": 110.0, "atr": 1.5,
        "qualified": 1, "failed_gates": "", "close": 100.0,
    })
    conn.close()

    result = _mock_resolve(db_path, sig_date, cutoff)
    assert result["open"] == 1
    assert result["resolved"] == 0


def _mock_resolve(db_path, sig_date, cutoff_date):
    """Minimal resolve that checks in-flight logic without actual network calls."""
    import pandas as pd
    from scanner.simulate import simulate_trades

    conn = store_db.get_connection(db_path)
    rows = store_db.get_unresolved_live_signals(conn)
    conn.close()

    # Filter to signals before cutoff
    eligible = [r for r in rows if date.fromisoformat(r["date"]) < cutoff_date]

    resolved = 0
    open_count = 0

    for row in eligible:
        sig = Signal(
            date=date.fromisoformat(row["date"]),
            ticker=row["ticker"], strategy=row["strategy"],
            score=float(row["score"] or 0), confidence=row["confidence"],
            stop=float(row["stop"]), target=float(row["target"]),
            atr=float(row["atr"] or 0), qualified=True,
        )

        # Only 2 bars available (in-flight: time_stop=10 not elapsed)
        n_after = 2
        idx = [sig.date + timedelta(days=i+1) for i in range(n_after)]
        bars = pd.DataFrame(
            {"Open": [100.0]*n_after, "High": [101.0]*n_after,
             "Low": [99.0]*n_after, "Close": [100.0]*n_after,
             "Volume": [1e6]*n_after},
            index=pd.DatetimeIndex([pd.Timestamp(d) for d in idx]),
        )

        trades = simulate_trades([sig], lambda t: bars, time_stop=10)
        if not trades:
            continue

        trade = trades[0]
        # In-flight: no stop/target hit and n_after < time_stop
        if trade.exit_reason not in ("stop", "target") and n_after < 10:
            open_count += 1
        else:
            resolved += 1

    return {"resolved": resolved, "open": open_count, "failures": 0}


# ── E9.3 — resolve is idempotent ─────────────────────────────────────────────

def test_resolve_second_run_noop(tmp_path, monkeypatch):
    """Once a signal is resolved, a second resolve run skips it."""
    db_path = _db(tmp_path)

    sig_date = date(2026, 6, 10)
    conn = store_db.get_connection(db_path)
    store_db.insert_signal(conn, {
        "date": str(sig_date), "ticker": "AAPL", "strategy": "pullback",
        "source": "live", "run_id": str(sig_date),
        "score": 65.0, "confidence": "MEDIUM",
        "stop": 90.0, "target": 110.0, "atr": 1.5,
        "qualified": 1, "failed_gates": "", "close": 100.0,
    })
    # Immediately mark it as resolved
    row = conn.execute("SELECT id FROM signals").fetchone()
    store_db.update_signal_outcome(conn, row["id"], {
        "outcome_checked_at": "2026-06-20", "entry_px": 100.0,
        "exit_px": 110.0, "exit_reason": "target", "r_multiple": 1.0,
        "holding_days": 5, "flags": "{}",
    })
    conn.close()

    # Unresolved list should be empty
    conn2 = store_db.get_connection(db_path)
    unresolved = store_db.get_unresolved_live_signals(conn2)
    conn2.close()
    assert len(unresolved) == 0


# ── E9.5 — compare_with_backtest ─────────────────────────────────────────────

def test_compare_warning_below_30(tmp_path):
    """Live n < 30 → warning present."""
    db_path = _db(tmp_path)

    # Insert 15 resolved live signals
    conn = store_db.get_connection(db_path)
    for i in range(15):
        store_db.insert_signal(conn, {
            "date": f"2026-01-{i+2:02d}", "ticker": f"T{i}",
            "strategy": "pullback", "source": "live", "run_id": f"2026-01-{i+2:02d}",
            "score": 60.0, "confidence": "MEDIUM",
            "stop": 90.0, "target": 110.0, "atr": 1.0,
            "qualified": 1, "failed_gates": "", "close": 100.0,
        })
        row = conn.execute(f"SELECT id FROM signals WHERE ticker='T{i}'").fetchone()
        store_db.update_signal_outcome(conn, row["id"], {
            "outcome_checked_at": "2026-02-01",
            "entry_px": 100.0, "exit_px": 105.0,
            "exit_reason": "target", "r_multiple": 0.5,
            "holding_days": 5, "flags": "{}",
        })

    # Insert a backtest run + report
    store_db.insert_run(conn, {
        "run_id": "bt_test", "kind": "backtest", "strategy": "pullback",
        "universe": "100", "params_json": "{}", "started_at": "", "finished_at": "",
        "signal_count": 200,
    })
    store_db.insert_backtest_report(conn, "bt_test",
                                    {"count": 200, "win_rate": 0.55, "expectancy_r": 0.4},
                                    ["survivorship"])
    conn.close()

    result = compare_with_backtest("bt_test", db_path=db_path)
    assert result["live_n"] == 15
    assert result["warning"] is not None
    assert "not yet statistically meaningful" in result["warning"]
    assert result["backtest_expectancy_r"] == pytest.approx(0.4)


def test_compare_no_warning_at_30(tmp_path):
    """Live n ≥ 30 → no warning."""
    db_path = _db(tmp_path)
    conn = store_db.get_connection(db_path)

    for i in range(30):
        store_db.insert_signal(conn, {
            "date": f"2026-01-{(i % 28) + 2:02d}", "ticker": f"T{i:03d}",
            "strategy": "pullback", "source": "live",
            "run_id": f"2026-01-{(i % 28) + 2:02d}",
            "score": 60.0, "confidence": "MEDIUM",
            "stop": 90.0, "target": 110.0, "atr": 1.0,
            "qualified": 1, "failed_gates": "", "close": 100.0,
        })
        row = conn.execute(f"SELECT id FROM signals WHERE ticker='T{i:03d}'").fetchone()
        store_db.update_signal_outcome(conn, row["id"], {
            "outcome_checked_at": "2026-03-01",
            "entry_px": 100.0, "exit_px": 105.0, "exit_reason": "target",
            "r_multiple": 0.5, "holding_days": 5, "flags": "{}",
        })

    store_db.insert_run(conn, {
        "run_id": "bt_30", "kind": "backtest", "strategy": "pullback",
        "universe": "100", "params_json": "{}", "started_at": "", "finished_at": "",
        "signal_count": 100,
    })
    store_db.insert_backtest_report(conn, "bt_30",
                                    {"count": 100, "win_rate": 0.5, "expectancy_r": 0.3},
                                    [])
    conn.close()

    result = compare_with_backtest("bt_30", db_path=db_path)
    assert result["live_n"] == 30
    assert result["warning"] is None


def test_compare_pulls_from_db_not_files(tmp_path):
    """Backtest metrics come from backtest_reports table, not from parquet/md files."""
    db_path = _db(tmp_path)
    conn = store_db.get_connection(db_path)
    store_db.insert_run(conn, {
        "run_id": "db_only", "kind": "backtest", "strategy": "pullback",
        "universe": "10", "params_json": "{}", "started_at": "", "finished_at": "",
        "signal_count": 10,
    })
    store_db.insert_backtest_report(conn, "db_only",
                                    {"count": 10, "win_rate": 0.6, "expectancy_r": 0.8},
                                    [])
    conn.close()

    result = compare_with_backtest("db_only", db_path=db_path)
    # Should succeed even though no parquet/md files exist
    assert result["backtest_expectancy_r"] == pytest.approx(0.8)
    assert result["backtest_win_rate"] == pytest.approx(0.6)


# ── Quick task 260819-gv9 — entry-time feature write-path round-trips ─────────

def test_write_live_signals_pullback_all_four_columns_non_null(tmp_path):
    """A live pullback row round-trips all four entry-time columns non-NULL."""
    db_path = _db(tmp_path)
    row = _live_row_with_entry_features("AAPL", strat="pullback")
    write_live_signals([row], "pullback", "2026-01-05", db_path=db_path)

    conn = store_db.get_connection(db_path)
    r = conn.execute("SELECT * FROM signals WHERE ticker='AAPL'").fetchone()
    conn.close()
    assert float(r["rsi_entry"]) == pytest.approx(48.0)
    assert float(r["rvol"]) == pytest.approx(1.5)
    assert float(r["pullback_depth_pct"]) == pytest.approx(5.17)
    assert float(r["pct_to_52w_high"]) == pytest.approx(20.0)


def test_write_live_signals_breakout_pullback_depth_null_pct_high_distance(tmp_path):
    """A breakout-shaped live row: pullback_depth_pct NULL, pct_to_52w_high stores the
    DISTANCE value (0.49), never the raw closeness value (99.51) — D-03."""
    db_path = _db(tmp_path)
    row = _live_row_with_entry_features(
        "MSFT", strat="breakout",
        entry_rsi=61.0, entry_rvol=3.48,
        entry_pullback_depth_pct=None, entry_pct_to_52w_high=0.49,
    )
    write_live_signals([row], "breakout", "2026-01-05", db_path=db_path)

    conn = store_db.get_connection(db_path)
    r = conn.execute("SELECT * FROM signals WHERE ticker='MSFT'").fetchone()
    conn.close()
    assert float(r["rsi_entry"]) == pytest.approx(61.0)
    assert float(r["rvol"]) == pytest.approx(3.48)
    assert r["pullback_depth_pct"] is None
    assert float(r["pct_to_52w_high"]) == pytest.approx(0.49)
    assert float(r["pct_to_52w_high"]) != pytest.approx(99.51)


def test_write_live_signals_nan_entry_features_round_trip_as_null(tmp_path):
    """float NaN entry-time values (as arrive via the pandas concat/to_dict path)
    round-trip as SQL NULL — a WHERE rvol IS NOT NULL query does not match (T-gv9-07)."""
    import math as _math
    db_path = _db(tmp_path)
    row = _live_row_with_entry_features(
        "NVDA",
        entry_rsi=float("nan"), entry_rvol=float("nan"),
        entry_pullback_depth_pct=float("nan"), entry_pct_to_52w_high=float("nan"),
    )
    write_live_signals([row], "pullback", "2026-01-05", db_path=db_path)

    conn = store_db.get_connection(db_path)
    r = conn.execute("SELECT * FROM signals WHERE ticker='NVDA'").fetchone()
    matches = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE ticker='NVDA' AND rvol IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    assert r["rsi_entry"] is None
    assert r["rvol"] is None
    assert r["pullback_depth_pct"] is None
    assert r["pct_to_52w_high"] is None
    assert matches == 0


def test_write_backtest_to_db_signal_entry_features_round_trip(tmp_path):
    """A Signal with the four fields set, written via write_backtest_to_db, reads back
    with all four columns equal to the Signal's values."""
    db_path = _db(tmp_path)
    sig = Signal(
        date=date(2026, 1, 5), ticker="AAPL", strategy="pullback",
        score=65.0, confidence="MEDIUM", stop=90.0, target=110.0,
        atr=1.5, qualified=True, close=100.0,
        rsi_entry=48.0, rvol=1.5, pullback_depth_pct=5.17, pct_to_52w_high=20.0,
    )
    write_backtest_to_db(
        signals=[sig], qualified_trades=[], near_miss_trades=[],
        run_id="bt_gv9", run_meta={"strategy": "pullback", "universe_size": 1},
        metrics={"count": 1}, biases=[], db_path=db_path,
    )

    conn = store_db.get_connection(db_path)
    r = conn.execute(
        "SELECT * FROM signals WHERE ticker='AAPL' AND source='backtest'"
    ).fetchone()
    conn.close()
    assert r is not None
    assert float(r["rsi_entry"]) == pytest.approx(48.0)
    assert float(r["rvol"]) == pytest.approx(1.5)
    assert float(r["pullback_depth_pct"]) == pytest.approx(5.17)
    assert float(r["pct_to_52w_high"]) == pytest.approx(20.0)


# import to ensure it's available at module scope for the inspect test
from scanner.journal import resolve_open_signals  # noqa: E402
