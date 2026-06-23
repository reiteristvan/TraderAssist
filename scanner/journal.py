"""E9.2-E9.5 — Live signal writer / resolver / compare (calls store_db).

Higher-level workflow module on top of store_db: writes live scan signals,
resolves outcomes against subsequent bars via the E7 simulator (zero
duplicated exit logic), and compares live vs backtest expectancy.
See CLAUDE.md EPIC E9.2-E9.5.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from scanner import store_db
from scanner.simulate import Signal, simulate_trades


# ── E9.2 — live signal writer ─────────────────────────────────────────────────

def write_live_signals(
    rows: list[dict],
    strategy: str,
    run_id: str,
    db_path: Optional[Path] = None,
) -> int:
    """Write qualifying live signals to scanner.db. Returns count inserted.

    run_id for live scans is the trading date string (YYYY-MM-DD) so
    re-scans on the same day produce no duplicates (INSERT OR IGNORE).
    """
    conn = store_db.get_connection(db_path)
    store_db.migrate(conn=conn)
    sigs = []
    for row in rows:
        sigs.append({
            "date": str(row.get("as_of") or row.get("date", date.today())),
            "ticker": row["ticker"],
            "strategy": strategy,
            "source": "live",
            "run_id": run_id,
            "score": row.get("score"),
            "confidence": row.get("confidence"),
            "stop": row.get("suggested_stop"),
            "target": row.get("suggested_target"),
            "atr": row.get("atr"),
            "qualified": 1 if row.get("qualified") else 0,
            "failed_gates": ";".join(row.get("failed_gates") or []),
            "close": row.get("close"),
            "gate_detail_json": json.dumps(row.get("gate_detail") or []),
        })
    n = store_db.insert_signals_batch(conn, sigs)
    conn.close()
    return n


# ── E9.3 — resolve open signals ───────────────────────────────────────────────

def resolve_open_signals(
    db_path: Optional[Path] = None,
    time_stop: int = 10,
) -> dict:
    """Resolve unresolved live signals that are at least 1 trading day old.

    Uses the E7 simulator (zero duplicated exit logic). In-flight signals —
    where stop/target haven't been hit and time_stop hasn't elapsed —
    remain unresolved. Idempotent: second run is a no-op.
    """
    from scanner.data_store import get_history, refresh_ticker
    from scanner.core import last_closed_session

    conn = store_db.get_connection(db_path)
    store_db.migrate(conn=conn)
    rows = store_db.get_unresolved_live_signals(conn)

    cutoff = last_closed_session()  # signals from strictly before this can be resolved
    eligible = [r for r in rows if date.fromisoformat(r["date"]) < cutoff]

    # Refresh each unique ticker once
    for ticker in sorted({r["ticker"] for r in eligible}):
        try:
            refresh_ticker(ticker)
        except Exception:
            pass

    resolved = 0
    open_count = 0
    failures = 0

    for row in eligible:
        try:
            sig = Signal(
                date=date.fromisoformat(row["date"]),
                ticker=row["ticker"],
                strategy=row["strategy"],
                score=float(row["score"] or 0),
                confidence=row.get("confidence"),
                stop=float(row["stop"]),
                target=float(row["target"]),
                atr=float(row["atr"] or 0),
                qualified=bool(row["qualified"]),
                failed_gates=[g for g in (row.get("failed_gates") or "").split(";") if g],
                close=float(row["close"] or 0),
            )

            bars = get_history(row["ticker"])
            if bars is None:
                failures += 1
                continue

            # Count bars after signal date to detect in-flight position
            import pandas as pd
            sig_ts = pd.Timestamp(sig.date)
            bars_after = bars[bars.index.normalize() > sig_ts.normalize()]
            n_after = len(bars_after)

            trades = simulate_trades([sig], lambda t: get_history(t), time_stop=time_stop)
            if not trades:
                failures += 1
                continue

            trade = trades[0]

            if trade.exit_reason == "incomplete":
                open_count += 1
                continue

            # In-flight: stop/target not hit and time_stop hasn't elapsed
            if trade.exit_reason not in ("stop", "target") and n_after < time_stop:
                open_count += 1
                continue

            outcome = {
                "outcome_checked_at": datetime.now().isoformat(),
                "entry_px": trade.entry_px,
                "exit_px": trade.exit_px,
                "exit_reason": trade.exit_reason,
                "r_multiple": trade.r_multiple,
                "holding_days": trade.holding_days,
                "flags": json.dumps(trade.flags),
            }
            store_db.update_signal_outcome(conn, row["id"], outcome)
            resolved += 1

        except Exception:
            failures += 1

    conn.close()
    return {"resolved": resolved, "open": open_count, "failures": failures}


# ── E9.5 — live vs backtest comparison ───────────────────────────────────────

def compare_with_backtest(
    run_id: str,
    db_path: Optional[Path] = None,
) -> dict:
    """Compare resolved live signals against a stored backtest run's metrics.

    Warns when live n < 30 (not yet statistically meaningful).
    Reads BOTH sides from the DB.
    """
    conn = store_db.get_connection(db_path)
    store_db.migrate(conn=conn)

    live_rows = store_db.get_live_resolved_signals(conn)
    report = store_db.get_run_report(conn, run_id)
    conn.close()

    live_n = len(live_rows)
    live_expectancy = None
    live_win_rate = None
    if live_rows:
        valid = [r for r in live_rows if r.get("r_multiple") is not None]
        if valid:
            rs = [float(r["r_multiple"]) for r in valid]
            live_expectancy = sum(rs) / len(rs)
            live_win_rate = sum(1 for r in rs if r > 0) / len(rs)

    bt_metrics = report["metrics"] if report else None
    bt_expectancy = bt_metrics.get("expectancy_r") if bt_metrics else None
    bt_win_rate = bt_metrics.get("win_rate") if bt_metrics else None
    bt_n = bt_metrics.get("count") if bt_metrics else None

    result = {
        "live_n": live_n,
        "live_expectancy_r": live_expectancy,
        "live_win_rate": live_win_rate,
        "backtest_run_id": run_id,
        "backtest_n": bt_n,
        "backtest_expectancy_r": bt_expectancy,
        "backtest_win_rate": bt_win_rate,
        "warning": "live n < 30 — not yet statistically meaningful" if live_n < 30 else None,
    }
    return result


# ── Helpers used by scan.py E9.4 ─────────────────────────────────────────────

def write_backtest_to_db(
    signals,
    qualified_trades,
    near_miss_trades,
    run_id: str,
    run_meta: dict,
    metrics: dict,
    biases: list,
    db_path: Optional[Path] = None,
) -> None:
    """Ingest a completed backtest run into scanner.db (E9.4)."""
    conn = store_db.get_connection(db_path)
    store_db.migrate(conn=conn)

    store_db.insert_run(conn, {
        "run_id": run_id,
        "kind": "backtest",
        "strategy": run_meta.get("strategy"),
        "universe": str(run_meta.get("universe_size")),
        "params_json": json.dumps(run_meta),
        "started_at": run_meta.get("started_at", ""),
        "finished_at": run_meta.get("finished_at", ""),
        "signal_count": len(signals),
    })

    sig_dicts = []
    for s in signals:
        sig_dicts.append({
            "date": str(s.date),
            "ticker": s.ticker,
            "strategy": s.strategy,
            "source": "backtest",
            "run_id": run_id,
            "score": s.score,
            "confidence": s.confidence,
            "stop": s.stop,
            "target": s.target,
            "atr": s.atr,
            "qualified": 1 if s.qualified else 0,
            "failed_gates": ";".join(s.failed_gates),
            "close": s.close,
        })
    store_db.insert_signals_batch(conn, sig_dicts)

    # Write trade outcomes for qualified signals
    for trade in qualified_trades + near_miss_trades:
        if trade.r_multiple is not None:
            # Find the signal row
            sig_id = store_db.get_signal_id_for_trade(
                conn, str(trade.signal_date), trade.ticker, run_id
            )
            if sig_id is not None:
                store_db.update_signal_outcome(conn, sig_id, {
                    "outcome_checked_at": datetime.now().isoformat(),
                    "entry_px": trade.entry_px,
                    "exit_px": trade.exit_px,
                    "exit_reason": trade.exit_reason,
                    "r_multiple": trade.r_multiple,
                    "holding_days": trade.holding_days,
                    "flags": json.dumps(trade.flags),
                })

    store_db.insert_backtest_report(conn, run_id, metrics, biases)
    conn.close()
