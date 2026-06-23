'use strict';

const request = require('supertest');
const db = require('../db');
const { makeTmpDb, cleanup } = require('./helpers');

function loadApp(dbPath) {
  jest.resetModules();
  const freshDb = require('../db');
  freshDb._reset();
  process.env.DB_PATH = dbPath;
  return require('../app');
}

// ── /api/stats/summary ────────────────────────────────────────────────────────

describe('GET /api/stats/summary', () => {
  let app, tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb({ withScanRun: true, withSignals: true, withResolved: true });
    app = loadApp(tmpDb);
  });
  afterAll(() => { db._reset(); cleanup(tmpDb); });

  it('returns 200 with expected keys', async () => {
    const res = await request(app).get('/api/stats/summary');
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('open_positions');
    expect(res.body).toHaveProperty('signals_tonight');
    expect(res.body).toHaveProperty('last_scan_run');
  });

  it('open_positions reflects unresolved live signals', async () => {
    const res = await request(app).get('/api/stats/summary');
    // AAPL resolved, MSFT open → 1 open position
    expect(res.body.open_positions).toBe(1);
  });

  it('signals_tonight reflects count for latest scan run', async () => {
    const res = await request(app).get('/api/stats/summary');
    expect(res.body.signals_tonight).toBe(2);
  });

  it('last_scan_run has run_id and started_at', async () => {
    const res = await request(app).get('/api/stats/summary');
    expect(res.body.last_scan_run.run_id).toBe('2026-06-22');
    expect(res.body.last_scan_run.started_at).toBe('2026-06-22T20:00:00');
  });

  it('returns 503 when DB missing', async () => {
    const noDbApp = loadApp('/nonexistent/scanner.db');
    const res = await request(noDbApp).get('/api/stats/summary');
    expect(res.status).toBe(503);
    db._reset();
  });
});

// ── /api/journal/compare ──────────────────────────────────────────────────────

describe('GET /api/journal/compare', () => {
  let app, tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb({ withScanRun: true, withBacktest: true,
                        withSignals: true, withResolved: true });
    app = loadApp(tmpDb);
  });
  afterAll(() => { db._reset(); cleanup(tmpDb); });

  it('requires backtest_run param', async () => {
    const res = await request(app).get('/api/journal/compare');
    expect(res.status).toBe(400);
  });

  it('returns 404 for unknown backtest run', async () => {
    const res = await request(app).get('/api/journal/compare?backtest_run=nope');
    expect(res.status).toBe(404);
  });

  it('returns comparison data for valid backtest run', async () => {
    const res = await request(app).get('/api/journal/compare?backtest_run=bt_2026_pb');
    expect(res.status).toBe(200);
    expect(res.body.backtest_run_id).toBe('bt_2026_pb');
    expect(res.body.backtest_expectancy_r).toBeCloseTo(0.38);
    expect(res.body.backtest_win_rate).toBeCloseTo(0.54);
    expect(typeof res.body.live_n).toBe('number');
  });

  it('includes warning when live_n < 30', async () => {
    const res = await request(app).get('/api/journal/compare?backtest_run=bt_2026_pb');
    // Only 1 resolved signal seeded (AAPL) → n < 30
    expect(res.body.live_n).toBe(1);
    expect(res.body.warning).not.toBeNull();
    expect(res.body.warning).toMatch(/not yet statistically meaningful/i);
  });

  it('warning is null when live_n >= 30', async () => {
    // Seed a DB with 30 resolved signals
    const bigDb = makeTmpDb({ withScanRun: false, withBacktest: true,
                               withSignals: false, withResolved: false });
    const Database = require('better-sqlite3');
    const conn = new Database(bigDb);
    for (let i = 0; i < 30; i++) {
      conn.prepare(
        `INSERT INTO signals (date, ticker, strategy, source, run_id,
          score, qualified, failed_gates, close, stop, target,
          exit_reason, r_multiple, entry_px, exit_px, holding_days, flags)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`
      ).run(`2026-01-${(i % 28 + 2).toString().padStart(2,'0')}`,
            `T${i.toString().padStart(3,'0')}`, 'pullback', 'live',
            `2026-01-${(i % 28 + 2).toString().padStart(2,'0')}`,
            60.0, 1, '', 100.0, 90.0, 110.0,
            'target', 0.5, 100.5, 110.0, 5, '{}');
    }
    conn.close();

    const bigApp = loadApp(bigDb);
    const res = await request(bigApp).get('/api/journal/compare?backtest_run=bt_2026_pb');
    expect(res.body.live_n).toBe(30);
    expect(res.body.warning).toBeNull();
    db._reset();
    const fs = require('fs');
    try { fs.unlinkSync(bigDb); } catch (_) {}
  });
});
