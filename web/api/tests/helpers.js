'use strict';

/**
 * Shared test DB factory — seeds a realistic scanner.db in a temp file.
 * Schema compatible with store_db.py v3 (has gate_detail_json, ath_zone).
 * Seeded data is written the same way Python store_db would write it,
 * proving schema compatibility across the language boundary (E12.2 AC1).
 */

const Database = require('better-sqlite3');
const path = require('path');
const os = require('os');
const fs = require('fs');

function makeTmpDb({ withScanRun = true, withBacktest = false, withSignals = true,
                     withResolved = false } = {}) {
  const tmpFile = path.join(os.tmpdir(), `ta_test_${Date.now()}_${Math.random().toString(36).slice(2)}.db`);
  const conn = new Database(tmpFile);

  conn.exec(`
    CREATE TABLE schema_version (version INTEGER NOT NULL);
    CREATE TABLE runs (
      run_id TEXT PRIMARY KEY, kind TEXT NOT NULL, strategy TEXT,
      universe TEXT, params_json TEXT,
      started_at TEXT, finished_at TEXT, signal_count INTEGER
    );
    CREATE TABLE signals (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date TEXT NOT NULL, ticker TEXT NOT NULL, strategy TEXT NOT NULL,
      source TEXT NOT NULL, run_id TEXT NOT NULL,
      score REAL, confidence TEXT, stop REAL, target REAL, atr REAL,
      qualified INTEGER NOT NULL DEFAULT 1, failed_gates TEXT, close REAL,
      gate_detail_json TEXT, ath_zone TEXT,
      outcome_checked_at TEXT, entry_px REAL, exit_px REAL,
      exit_reason TEXT, r_multiple REAL, holding_days INTEGER, flags TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      UNIQUE (date, ticker, strategy, source, run_id)
    );
    CREATE TABLE backtest_reports (
      run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
      metrics_json TEXT, biases_json TEXT
    );
    INSERT INTO schema_version VALUES (3);
  `);

  if (withScanRun) {
    conn.prepare(
      "INSERT INTO runs (run_id, kind, strategy, started_at, finished_at, signal_count) VALUES (?,?,?,?,?,?)"
    ).run('2026-06-22', 'scan', 'pullback', '2026-06-22T20:00:00', '2026-06-22T20:01:30', 2);
  }

  if (withBacktest) {
    conn.prepare(
      "INSERT INTO runs (run_id, kind, strategy, universe, params_json, started_at, finished_at, signal_count) VALUES (?,?,?,?,?,?,?,?)"
    ).run('bt_2026_pb', 'backtest', 'pullback', 'sp600.txt',
          JSON.stringify({ start: '2023-01-01', end: '2025-12-31' }),
          '2026-06-22T10:00:00', '2026-06-22T10:45:00', 180);
    conn.prepare(
      "INSERT INTO backtest_reports (run_id, metrics_json, biases_json) VALUES (?,?,?)"
    ).run('bt_2026_pb',
          JSON.stringify({ count: 180, win_rate: 0.54, expectancy_r: 0.38, median_holding_days: 7 }),
          JSON.stringify(['Survivorship bias — currently listed names only',
                          'Fundamentals look-ahead bias']));
  }

  const gateDetail = JSON.stringify([
    { name: 'Trend alignment', status: 'pass', detail: 'close > SMA50 > SMA200' },
    { name: 'RSI in range',    status: 'pass', detail: '52.3' },
    { name: 'Earnings clear',  status: 'skip', detail: 'no earnings data' },
    { name: 'Profitable',      status: 'pass', detail: '' },
    { name: 'RS line at 60d high', status: 'bonus_pass', detail: '' },
  ]);

  if (withSignals && withScanRun) {
    conn.prepare(
      `INSERT INTO signals (date, ticker, strategy, source, run_id, score, confidence,
        stop, target, atr, qualified, failed_gates, close, gate_detail_json, ath_zone)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`
    ).run('2026-06-22', 'AAPL', 'pullback', 'live', '2026-06-22',
          72.5, 'HIGH', 175.0, 200.0, 2.8, 1, '', 180.0, gateDetail, 'NEAR_ATH');

    conn.prepare(
      `INSERT INTO signals (date, ticker, strategy, source, run_id, score, confidence,
        stop, target, atr, qualified, failed_gates, close, gate_detail_json, ath_zone)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`
    ).run('2026-06-22', 'MSFT', 'pullback', 'live', '2026-06-22',
          61.0, 'MEDIUM', 390.0, 440.0, 5.1, 1, '', 400.0, null, null);

    if (withResolved) {
      // Resolve AAPL
      conn.prepare(
        `UPDATE signals SET outcome_checked_at=?, entry_px=?, exit_px=?,
         exit_reason=?, r_multiple=?, holding_days=?, flags=?
         WHERE ticker='AAPL' AND source='live'`
      ).run('2026-07-02T12:00:00', 181.0, 200.0, 'target', 0.76, 8, '{}');
    }
  }

  conn.close();
  return tmpFile;
}

function cleanup(file) {
  try { fs.unlinkSync(file); } catch (_) {}
}

module.exports = { makeTmpDb, cleanup };
