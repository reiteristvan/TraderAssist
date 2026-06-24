'use strict';

/**
 * db/index.js — owns ALL SQL for the API layer.
 *
 * Mirrors the Python store_db discipline: no SQL string literals anywhere
 * else in the app. Opens scanner.db READ-ONLY; never writes.
 *
 * The connection is lazily initialised on first use and cached. If the DB
 * file does not exist yet, getDb() returns null — callers must handle that
 * case and respond with 503 rather than letting the process crash.
 */

const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

let _db = null;
let _writeDb = null;
let _dbPath = null;

function resolvedDbPath() {
  return process.env.DB_PATH
    ? path.resolve(process.env.DB_PATH)
    : path.resolve(__dirname, '..', '..', '..', 'data', 'scanner.db');
}

/**
 * Returns an open read-only Database, or null if the file is absent/unreadable.
 * Caches the connection once successfully opened.
 */
function getDb() {
  if (_db) return _db;

  const dbPath = resolvedDbPath();
  _dbPath = dbPath;

  if (!fs.existsSync(dbPath)) return null;

  try {
    _db = new Database(dbPath, { readonly: true, fileMustExist: true });
    return _db;
  } catch (_err) {
    return null;
  }
}

/**
 * Returns a read-write Database for job enqueueing only.
 * Separate from the read-only connection to keep all query functions protected.
 */
function getWriteDb() {
  if (_writeDb) return _writeDb;
  const dbPath = resolvedDbPath();
  if (!fs.existsSync(dbPath)) return null;
  try {
    _writeDb = new Database(dbPath, { fileMustExist: true });
    _applyMigrations(_writeDb);
    return _writeDb;
  } catch (_) {
    return null;
  }
}

/**
 * Applies any schema migrations the Python migrate() hasn't run yet.
 * Safe to call repeatedly — each step is guarded by a column/version check.
 */
function _applyMigrations(db) {
  const cols = db.prepare('PRAGMA table_info(signals)').all().map(r => r.name);
  if (!cols.includes('notes')) {
    db.prepare('ALTER TABLE signals ADD COLUMN notes TEXT').run();
    db.prepare('UPDATE schema_version SET version = 6').run();
  }
}

/** Expose the resolved path for diagnostic messages even when DB is missing. */
function getDbPath() {
  return _dbPath || resolvedDbPath();
}

/** Reset cached connections — used in tests to swap DB paths. */
function _reset() {
  if (_db) { try { _db.close(); } catch (_) {} }
  if (_writeDb) { try { _writeDb.close(); } catch (_) {} }
  _db = null;
  _writeDb = null;
  _dbPath = null;
}

// ── Queries (all SQL lives here) ─────────────────────────────────────────────

function getSchemaVersion() {
  const db = getDb();
  if (!db) return null;
  const row = db.prepare('SELECT version FROM schema_version LIMIT 1').get();
  return row ? row.version : null;
}

function getLastScanRun() {
  const db = getDb();
  if (!db) return null;
  return db.prepare(
    "SELECT run_id, started_at, finished_at, signal_count, strategy, universe " +
    "FROM runs WHERE kind = 'scan' ORDER BY started_at DESC LIMIT 1"
  ).get() || null;
}

function getLatestSignals({ strategy, minScore, confidence } = {}) {
  const db = getDb();
  if (!db) return null;

  // Find the most recent live scan run_id
  const latestRun = db.prepare(
    "SELECT run_id FROM runs WHERE kind = 'scan' ORDER BY started_at DESC LIMIT 1"
  ).get();
  if (!latestRun) return [];

  const conditions = [
    "source = 'live'",
    "qualified = 1",
    "run_id = ?",
  ];
  const params = [latestRun.run_id];

  if (strategy) { conditions.push('strategy = ?'); params.push(strategy); }
  if (minScore != null) { conditions.push('score >= ?'); params.push(Number(minScore)); }
  if (confidence) { conditions.push('confidence = ?'); params.push(confidence.toUpperCase()); }

  return db.prepare(
    'SELECT * FROM signals WHERE ' + conditions.join(' AND ') +
    ' ORDER BY score DESC'
  ).all(...params).map(_parseSignalJson);
}

function getSignalById(id) {
  const db = getDb();
  if (!db) return null;
  const row = db.prepare('SELECT * FROM signals WHERE id = ?').get(Number(id));
  if (!row) return null;
  return _parseSignalJson(row);
}

function _parseSignalJson(row) {
  const out = Object.assign({}, row);
  if (out.gate_detail_json) {
    try { out.gate_detail = JSON.parse(out.gate_detail_json); }
    catch (_) { out.gate_detail = []; }
    delete out.gate_detail_json;
  } else {
    out.gate_detail = [];
  }
  return out;
}

function getSignalHistory({ from, to, status, strategy } = {}) {
  const db = getDb();
  if (!db) return null;

  const conditions = ["source = 'live'"];
  const params = [];

  if (from) { conditions.push('date >= ?'); params.push(from); }
  if (to)   { conditions.push('date <= ?'); params.push(to); }
  if (strategy) { conditions.push('strategy = ?'); params.push(strategy); }

  if (status === 'open')     { conditions.push('exit_reason IS NULL'); }
  if (status === 'resolved') { conditions.push('exit_reason IS NOT NULL'); }

  return db.prepare(
    'SELECT * FROM signals WHERE ' + conditions.join(' AND ') +
    ' ORDER BY date DESC'
  ).all(...params).map(_parseSignalJson);
}

function getRuns(kind) {
  const db = getDb();
  if (!db) return null;
  if (kind) {
    return db.prepare(
      'SELECT * FROM runs WHERE kind = ? ORDER BY started_at DESC'
    ).all(kind);
  }
  return db.prepare('SELECT * FROM runs ORDER BY started_at DESC').all();
}

function getRunById(runId) {
  const db = getDb();
  if (!db) return null;
  return db.prepare('SELECT * FROM runs WHERE run_id = ?').get(runId) || null;
}

function getBacktestReport(runId) {
  const db = getDb();
  if (!db) return null;
  return db.prepare(
    'SELECT * FROM backtest_reports WHERE run_id = ?'
  ).get(runId) || null;
}

function getResolvedLiveSignals() {
  const db = getDb();
  if (!db) return null;
  return db.prepare(
    "SELECT * FROM signals WHERE source = 'live' AND qualified = 1 AND exit_reason IS NOT NULL"
  ).all();
}

function getSummaryStats() {
  const db = getDb();
  if (!db) return null;

  const openPositions = db.prepare(
    "SELECT COUNT(*) AS n FROM signals WHERE source='live' AND qualified=1 AND exit_reason IS NULL"
  ).get().n;

  const lastScan = db.prepare(
    "SELECT run_id, started_at, finished_at, signal_count, strategy " +
    "FROM runs WHERE kind='scan' ORDER BY started_at DESC LIMIT 1"
  ).get() || null;

  const tonightCount = lastScan
    ? db.prepare(
        "SELECT COUNT(*) AS n FROM signals WHERE source='live' AND qualified=1 AND run_id = ?"
      ).get(lastScan.run_id).n
    : 0;

  return {
    open_positions: openPositions,
    signals_tonight: tonightCount,
    last_scan_run: lastScan || null,
  };
}

function getJournalCompare(runId) {
  const db = getDb();
  if (!db) return null;

  const report = getBacktestReport(runId);
  if (!report) return null;

  const reportData = JSON.parse(report.metrics_json || '{}');
  // Support both old flat format and new nested format (full json_data from render_report)
  const btMetrics = reportData.metrics || reportData;
  const liveRows = db.prepare(
    "SELECT r_multiple FROM signals " +
    "WHERE source='live' AND qualified=1 AND exit_reason IS NOT NULL AND r_multiple IS NOT NULL"
  ).all();

  const liveN = liveRows.length;
  let liveExpectancy = null;
  let liveWinRate = null;

  if (liveN > 0) {
    liveExpectancy = liveRows.reduce((s, r) => s + r.r_multiple, 0) / liveN;
    liveWinRate = liveRows.filter(r => r.r_multiple > 0).length / liveN;
  }

  return {
    live_n: liveN,
    live_expectancy_r: liveExpectancy !== null ? Math.round(liveExpectancy * 1000) / 1000 : null,
    live_win_rate: liveWinRate !== null ? Math.round(liveWinRate * 1000) / 1000 : null,
    backtest_run_id: runId,
    backtest_n: btMetrics.count || null,
    backtest_expectancy_r: btMetrics.expectancy_r != null ? btMetrics.expectancy_r : null,
    backtest_win_rate: btMetrics.win_rate != null ? btMetrics.win_rate : null,
    warning: liveN < 30
      ? `Live sample (n=${liveN}) not yet statistically meaningful — need ≥30 resolved signals`
      : null,
  };
}

// ── Signal outcome write ─────────────────────────────────────────────────────

function updateSignalOutcome(id, { exit_reason, entry_px, exit_px, r_multiple, holding_days, notes }) {
  const writeDb = getWriteDb();
  if (!writeDb) return null;
  const now = new Date().toISOString();
  writeDb.prepare(
    `UPDATE signals
     SET exit_reason=?, entry_px=?, exit_px=?, r_multiple=?, holding_days=?, outcome_checked_at=?, notes=?
     WHERE id=? AND source='live'`
  ).run(
    exit_reason,
    entry_px   != null ? Number(entry_px)    : null,
    exit_px    != null ? Number(exit_px)     : null,
    r_multiple != null ? Number(r_multiple)  : null,
    holding_days != null ? Number(holding_days) : null,
    now,
    notes != null ? String(notes) : null,
    id
  );
  const row = writeDb.prepare('SELECT * FROM signals WHERE id = ?').get(id);
  if (!row) return null;
  return _parseSignalJson(row);
}

// ── OHLCV bars (E12.7) ───────────────────────────────────────────────────────

function getOhlcv(ticker, limit = 120) {
  const db = getDb();
  if (!db) return null;
  const rows = db.prepare(
    'SELECT date, open, high, low, close, volume FROM bars WHERE ticker = ? ORDER BY date DESC LIMIT ?'
  ).all(ticker.toUpperCase(), Math.min(limit, 500));
  return rows.reverse();
}

// ── Jobs (write path — uses getWriteDb) ─────────────────────────────────────

function enqueueJob(kind, params) {
  const db = getWriteDb();
  if (!db) return null;
  const result = db.prepare(
    "INSERT INTO jobs (kind, params_json) VALUES (?, ?)"
  ).run(kind, JSON.stringify(params || {}));
  return { id: Number(result.lastInsertRowid), status: 'queued' };
}

function getJob(id) {
  const db = getDb();
  if (!db) return null;
  return db.prepare('SELECT * FROM jobs WHERE id = ?').get(Number(id)) || null;
}

module.exports = {
  getDb,
  getDbPath,
  _reset,
  getSchemaVersion,
  getLastScanRun,
  getLatestSignals,
  getSignalById,
  getSignalHistory,
  getRuns,
  getRunById,
  getBacktestReport,
  getResolvedLiveSignals,
  getSummaryStats,
  getJournalCompare,
  getOhlcv,
  updateSignalOutcome,
  enqueueJob,
  getJob,
};
