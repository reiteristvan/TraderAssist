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
    CREATE TABLE jobs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      kind TEXT NOT NULL, params_json TEXT,
      status TEXT NOT NULL DEFAULT 'queued',
      result_ref TEXT, claimed_at TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      finished_at TEXT
    );
    INSERT INTO schema_version VALUES (4);
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
      JSON.stringify({
        metrics: {
          count: 180, win_rate: 0.54, expectancy_r: 0.38, avg_win_r: 1.9, avg_loss_r: -1.0,
          median_holding_days: 7, max_drawdown_r: 2.8,
          exit_reason_breakdown: { stop: 83, target: 97 },
          ambiguous_bar_pct: 0.04, gap_skip_pct: 0.06, incomplete_pct: 0.02,
        },
        score_buckets: [
          { bucket: '40–54', n: 12, win_rate: 0.42, expectancy_r: 0.12, verdict: 'insufficient n' },
          { bucket: '55–69', n: 45, win_rate: 0.49, expectancy_r: 0.28, verdict: 'ok' },
          { bucket: '70–84', n: 82, win_rate: 0.57, expectancy_r: 0.41, verdict: 'ok' },
          { bucket: '85–100', n: 41, win_rate: 0.66, expectancy_r: 0.62, verdict: 'ok' },
        ],
        conf_buckets: [
          { bucket: 'LOW',    n: 22, win_rate: 0.36, expectancy_r: 0.08, verdict: 'ok' },
          { bucket: 'MEDIUM', n: 78, win_rate: 0.51, expectancy_r: 0.32, verdict: 'ok' },
          { bucket: 'HIGH',   n: 80, win_rate: 0.64, expectancy_r: 0.55, verdict: 'ok' },
        ],
        gate_attribution: [
          { gate: 'Volume contraction', n: 35, expectancy_r: 0.40, qualified_expectancy_r: 0.38, delta_r: 0.02, verdict: 'no measurable value in this sample' },
          { gate: 'ADX(14) trend strength', n: 28, expectancy_r: 0.18, qualified_expectancy_r: 0.38, delta_r: -0.20, verdict: 'insufficient n' },
        ],
        monthly_signals: { '2023-01': 5, '2023-02': 8 },
        run_meta: { strategy: 'pullback', start: '2023-01-01', end: '2025-12-31' },
      }),
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
