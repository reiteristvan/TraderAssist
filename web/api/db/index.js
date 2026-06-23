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

/** Expose the resolved path for diagnostic messages even when DB is missing. */
function getDbPath() {
  return _dbPath || resolvedDbPath();
}

/** Reset cached connection — used in tests to swap DB paths. */
function _reset() {
  if (_db) { try { _db.close(); } catch (_) {} }
  _db = null;
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

  const btMetrics = JSON.parse(report.metrics_json || '{}');
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
};
