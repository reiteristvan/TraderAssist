"""E9.1 — Owns ALL SQL; data/scanner.db (SQLite, Postgres-swappable).

Single module with the DB connection and every SQL statement. Tables use
portable types only (TEXT/INTEGER/REAL, ISO-8601 date strings). No ORM.
See CLAUDE.md EPIC E9.1.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

_DEFAULT_DB = Path("data/scanner.db")
_SCHEMA_VERSION = 9

# ── DDL ───────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id     TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    strategy   TEXT,
    universe   TEXT,
    params_json TEXT,
    started_at  TEXT,
    finished_at TEXT,
    signal_count INTEGER
);

CREATE TABLE IF NOT EXISTS signals (
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
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (date, ticker, strategy, source, run_id)
);

CREATE TABLE IF NOT EXISTS backtest_reports (
    run_id       TEXT PRIMARY KEY REFERENCES runs(run_id),
    metrics_json TEXT,
    biases_json  TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    params_json TEXT,
    status      TEXT NOT NULL DEFAULT 'queued',
    result_ref  TEXT,
    claimed_at  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS bars (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    open   REAL,
    high   REAL,
    low    REAL,
    close  REAL,
    volume REAL,
    PRIMARY KEY (ticker, date)
);
"""

# ── Connection ────────────────────────────────────────────────────────────────

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return a sqlite3 connection with foreign-key enforcement enabled."""
    path = Path(db_path) if db_path else _DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(db_path: Optional[Path] = None, conn: Optional[sqlite3.Connection] = None) -> None:
    """Create tables if absent and run incremental migrations. Idempotent."""
    own = conn is None
    if own:
        conn = get_connection(db_path)
    try:
        conn.executescript(_DDL)
        ver = conn.execute("SELECT version FROM schema_version").fetchone()
        current = int(ver["version"]) if ver else 0
        if ver is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (_SCHEMA_VERSION,))
        else:
            if current < 2:
                conn.execute("ALTER TABLE signals ADD COLUMN gate_detail_json TEXT")
                conn.execute("UPDATE schema_version SET version = 2")
                current = 2
            if current < 3:
                conn.execute("ALTER TABLE signals ADD COLUMN ath_zone TEXT")
                conn.execute("UPDATE schema_version SET version = 3")
                current = 3
            if current < 4:
                # jobs table already created by executescript(_DDL) above
                conn.execute("UPDATE schema_version SET version = 4")
                current = 4
            if current < 5:
                # bars table already created by executescript(_DDL) above
                conn.execute("UPDATE schema_version SET version = 5")
                current = 5
            if current < 6:
                conn.execute("ALTER TABLE signals ADD COLUMN notes TEXT")
                conn.execute("UPDATE schema_version SET version = 6")
                current = 6
            if current < 7:
                conn.execute("ALTER TABLE signals ADD COLUMN target_r REAL")
                conn.execute("ALTER TABLE signals ADD COLUMN target_atr REAL")
                conn.execute("UPDATE schema_version SET version = 7")
                current = 7
            if current < 8:
                conn.execute("ALTER TABLE signals ADD COLUMN mae_r REAL")
                conn.execute("ALTER TABLE signals ADD COLUMN mfe_r REAL")
                conn.execute("ALTER TABLE signals ADD COLUMN post_stop_reached_target INTEGER")
                conn.execute("ALTER TABLE signals ADD COLUMN post_stop_mfe_r REAL")
                conn.execute("UPDATE schema_version SET version = 8")
                current = 8
            if current < 9:
                conn.execute("ALTER TABLE signals ADD COLUMN industry_group TEXT")
                conn.execute("ALTER TABLE signals ADD COLUMN industry_momentum REAL")
                conn.execute("ALTER TABLE signals ADD COLUMN industry_above_50ma INTEGER")
                conn.execute("ALTER TABLE signals ADD COLUMN industry_rank_pct REAL")
                conn.execute("UPDATE schema_version SET version = 9")
                current = 9  # noqa: F841 (used for future migration guards)
        conn.commit()
    finally:
        if own:
            conn.close()


def get_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    return int(row["version"]) if row else 0


# ── runs ──────────────────────────────────────────────────────────────────────

def insert_run(conn: sqlite3.Connection, run: dict) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO runs
           (run_id, kind, strategy, universe, params_json, started_at, finished_at, signal_count)
           VALUES (:run_id, :kind, :strategy, :universe, :params_json,
                   :started_at, :finished_at, :signal_count)""",
        run,
    )
    conn.commit()


def update_run_finished(conn: sqlite3.Connection, run_id: str,
                        finished_at: str, signal_count: int) -> None:
    conn.execute(
        "UPDATE runs SET finished_at = ?, signal_count = ? WHERE run_id = ?",
        (finished_at, signal_count, run_id),
    )
    conn.commit()


def get_backtest_runs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM runs WHERE kind = 'backtest' ORDER BY started_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


# ── signals ───────────────────────────────────────────────────────────────────

def insert_signal(conn: sqlite3.Connection, sig: dict) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO signals
           (date, ticker, strategy, source, run_id, score, confidence,
            stop, target, atr, qualified, failed_gates, close,
            gate_detail_json, ath_zone,
            industry_group, industry_momentum, industry_above_50ma, industry_rank_pct)
           VALUES (:date, :ticker, :strategy, :source, :run_id, :score, :confidence,
                   :stop, :target, :atr, :qualified, :failed_gates, :close,
                   :gate_detail_json, :ath_zone,
                   :industry_group, :industry_momentum,
                   :industry_above_50ma, :industry_rank_pct)""",
        {
            **sig,
            "gate_detail_json": sig.get("gate_detail_json"),
            "ath_zone": sig.get("ath_zone"),
            "industry_group": sig.get("industry_group"),
            "industry_momentum": sig.get("industry_momentum"),
            "industry_above_50ma": sig.get("industry_above_50ma"),
            "industry_rank_pct": sig.get("industry_rank_pct"),
        },
    )
    conn.commit()


def insert_signals_batch(conn: sqlite3.Connection, sigs: list[dict]) -> int:
    """Insert a batch of signals. Returns count inserted (ignores duplicates)."""
    inserted = 0
    for sig in sigs:
        cur = conn.execute(
            """INSERT OR IGNORE INTO signals
               (date, ticker, strategy, source, run_id, score, confidence,
                stop, target, atr, qualified, failed_gates, close,
                gate_detail_json, ath_zone,
                industry_group, industry_momentum, industry_above_50ma, industry_rank_pct)
               VALUES (:date, :ticker, :strategy, :source, :run_id, :score, :confidence,
                       :stop, :target, :atr, :qualified, :failed_gates, :close,
                       :gate_detail_json, :ath_zone,
                       :industry_group, :industry_momentum,
                       :industry_above_50ma, :industry_rank_pct)""",
            {
                **sig,
                "gate_detail_json": sig.get("gate_detail_json"),
                "ath_zone": sig.get("ath_zone"),
                "industry_group": sig.get("industry_group"),
                "industry_momentum": sig.get("industry_momentum"),
                "industry_above_50ma": sig.get("industry_above_50ma"),
                "industry_rank_pct": sig.get("industry_rank_pct"),
            },
        )
        inserted += cur.rowcount
    conn.commit()
    return inserted


def get_unresolved_live_signals(conn: sqlite3.Connection) -> list[dict]:
    """Live signals without an outcome (exit_reason IS NULL, source='live')."""
    rows = conn.execute(
        """SELECT * FROM signals
           WHERE source = 'live' AND qualified = 1 AND exit_reason IS NULL
           ORDER BY date ASC""",
    ).fetchall()
    return [dict(r) for r in rows]


def get_live_resolved_signals(conn: sqlite3.Connection) -> list[dict]:
    """Live signals that have been resolved (exit_reason IS NOT NULL)."""
    rows = conn.execute(
        """SELECT * FROM signals
           WHERE source = 'live' AND qualified = 1 AND exit_reason IS NOT NULL""",
    ).fetchall()
    return [dict(r) for r in rows]


def update_signal_outcome(conn: sqlite3.Connection, signal_id: int, outcome: dict) -> None:
    merged = {
        "target_r": None, "target_atr": None,
        "mae_r": None, "mfe_r": None,
        "post_stop_reached_target": None, "post_stop_mfe_r": None,
        **outcome,
    }
    conn.execute(
        """UPDATE signals SET
               outcome_checked_at = :outcome_checked_at,
               entry_px    = :entry_px,
               exit_px     = :exit_px,
               exit_reason = :exit_reason,
               r_multiple  = :r_multiple,
               holding_days = :holding_days,
               flags       = :flags,
               target_r    = :target_r,
               target_atr  = :target_atr,
               mae_r       = :mae_r,
               mfe_r       = :mfe_r,
               post_stop_reached_target = :post_stop_reached_target,
               post_stop_mfe_r = :post_stop_mfe_r
           WHERE id = :id""",
        {**merged, "id": signal_id},
    )
    conn.commit()


# ── backtest_reports ──────────────────────────────────────────────────────────

def insert_backtest_report(conn: sqlite3.Connection, run_id: str,
                           metrics: dict, biases: list) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO backtest_reports (run_id, metrics_json, biases_json)
           VALUES (?, ?, ?)""",
        (run_id, json.dumps(metrics), json.dumps(biases)),
    )
    conn.commit()


def get_signal_id_for_trade(conn: sqlite3.Connection,
                            signal_date: str, ticker: str, run_id: str) -> Optional[int]:
    """Look up signal id by date/ticker/run_id (source='backtest')."""
    row = conn.execute(
        "SELECT id FROM signals WHERE date=? AND ticker=? AND source='backtest' AND run_id=?",
        (signal_date, ticker, run_id),
    ).fetchone()
    return int(row["id"]) if row else None


def get_run_report(conn: sqlite3.Connection, run_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM backtest_reports WHERE run_id = ?", (run_id,)
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("metrics_json"):
        d["metrics"] = json.loads(d["metrics_json"])
    if d.get("biases_json"):
        d["biases"] = json.loads(d["biases_json"])
    return d


# ── jobs ──────────────────────────────────────────────────────────────────────

def enqueue_job(conn: sqlite3.Connection, kind: str, params: dict) -> int:
    """Insert a new queued job; returns the job id."""
    cur = conn.execute(
        "INSERT INTO jobs (kind, params_json) VALUES (?, ?)",
        (kind, json.dumps(params)),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def claim_next_job(conn: sqlite3.Connection) -> Optional[dict]:
    """Atomically claim the oldest queued job. Returns the job dict or None."""
    conn.execute(
        """UPDATE jobs SET status='running', claimed_at=datetime('now')
           WHERE id=(SELECT id FROM jobs WHERE status='queued' ORDER BY id LIMIT 1)"""
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM jobs WHERE status='running' ORDER BY claimed_at DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def complete_job(conn: sqlite3.Connection, job_id: int, result_ref: str) -> None:
    """Mark a job as done with a result reference."""
    conn.execute(
        "UPDATE jobs SET status='done', result_ref=?, finished_at=datetime('now') WHERE id=?",
        (result_ref, job_id),
    )
    conn.commit()


def fail_job(conn: sqlite3.Connection, job_id: int, error_msg: str) -> None:
    """Mark a job as errored; error message stored in result_ref."""
    conn.execute(
        "UPDATE jobs SET status='error', result_ref=?, finished_at=datetime('now') WHERE id=?",
        (error_msg[:2000], job_id),
    )
    conn.commit()


def get_job(conn: sqlite3.Connection, job_id: int) -> Optional[dict]:
    """Return a job by id, or None if not found."""
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def reset_stale_jobs(conn: sqlite3.Connection, timeout_seconds: int = 300) -> int:
    """Re-queue jobs stuck in 'running' for longer than timeout_seconds (crash recovery)."""
    cur = conn.execute(
        """UPDATE jobs SET status='queued', claimed_at=NULL
           WHERE status='running'
           AND (julianday('now') - julianday(claimed_at)) * 86400 > ?""",
        (timeout_seconds,),
    )
    conn.commit()
    return cur.rowcount


# ── bars (E12.7 — OHLCV snapshot for chart) ──────────────────────────────────

def upsert_bars(conn: sqlite3.Connection, ticker: str, rows: list[dict]) -> None:
    """Insert or replace OHLCV bars for a ticker (recent window, for the chart)."""
    upper = ticker.upper()
    normalized = [{**r, "ticker": upper} for r in rows]
    conn.executemany(
        """INSERT OR REPLACE INTO bars (ticker, date, open, high, low, close, volume)
           VALUES (:ticker, :date, :open, :high, :low, :close, :volume)""",
        normalized,
    )
    conn.commit()


def get_ohlcv(conn: sqlite3.Connection, ticker: str, limit: int = 120) -> list[dict]:
    """Return the most recent `limit` OHLCV bars for `ticker`, chronological order."""
    rows = conn.execute(
        """SELECT date, open, high, low, close, volume FROM bars
           WHERE ticker = ? ORDER BY date DESC LIMIT ?""",
        (ticker.upper(), limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]
