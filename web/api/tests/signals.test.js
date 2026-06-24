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

// ── /api/signals/latest ───────────────────────────────────────────────────────

describe('GET /api/signals/latest', () => {
  let app, tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb({ withScanRun: true, withSignals: true });
    app = loadApp(tmpDb);
  });
  afterAll(() => { db._reset(); cleanup(tmpDb); });

  it('returns 200 with count and signals array', async () => {
    const res = await request(app).get('/api/signals/latest');
    expect(res.status).toBe(200);
    expect(typeof res.body.count).toBe('number');
    expect(Array.isArray(res.body.signals)).toBe(true);
  });

  it('returns qualified signals for the latest scan run', async () => {
    const res = await request(app).get('/api/signals/latest');
    expect(res.body.count).toBe(2);
    expect(res.body.signals.every(s => s.qualified === 1)).toBe(true);
  });

  it('includes expected fields: ticker, score, confidence, stop, target, atr, ath_zone', async () => {
    const res = await request(app).get('/api/signals/latest');
    const s = res.body.signals[0];
    expect(s).toHaveProperty('ticker');
    expect(s).toHaveProperty('score');
    expect(s).toHaveProperty('confidence');
    expect(s).toHaveProperty('stop');
    expect(s).toHaveProperty('target');
    expect(s).toHaveProperty('atr');
    expect(s).toHaveProperty('ath_zone');
  });

  it('includes gate_detail as parsed array (not raw JSON string)', async () => {
    const res = await request(app).get('/api/signals/latest');
    const aapl = res.body.signals.find(s => s.ticker === 'AAPL');
    expect(Array.isArray(aapl.gate_detail)).toBe(true);
    expect(aapl.gate_detail.length).toBeGreaterThan(0);
    expect(aapl.gate_detail[0]).toHaveProperty('name');
    expect(aapl.gate_detail[0]).toHaveProperty('status');
  });

  it('filters by strategy', async () => {
    const res = await request(app).get('/api/signals/latest?strategy=pullback');
    expect(res.status).toBe(200);
    expect(res.body.signals.every(s => s.strategy === 'pullback')).toBe(true);
  });

  it('filters by min_score', async () => {
    const res = await request(app).get('/api/signals/latest?min_score=70');
    expect(res.status).toBe(200);
    expect(res.body.signals.every(s => s.score >= 70)).toBe(true);
    expect(res.body.count).toBe(1); // only AAPL at 72.5
  });

  it('filters by confidence', async () => {
    const res = await request(app).get('/api/signals/latest?confidence=HIGH');
    expect(res.status).toBe(200);
    expect(res.body.signals.every(s => s.confidence === 'HIGH')).toBe(true);
    expect(res.body.count).toBe(1); // only AAPL
  });

  it('returns empty list when no scan runs exist', async () => {
    const emptyDb = makeTmpDb({ withScanRun: false, withSignals: false });
    const emptyApp = loadApp(emptyDb);
    const res = await request(emptyApp).get('/api/signals/latest');
    expect(res.status).toBe(200);
    expect(res.body.count).toBe(0);
    db._reset();
    cleanup(emptyDb);
  });

  it('returns 503 when DB is missing', async () => {
    const noDbApp = loadApp('/nonexistent/scanner.db');
    const res = await request(noDbApp).get('/api/signals/latest');
    expect(res.status).toBe(503);
    db._reset();
  });
});

// ── /api/signals/:id ─────────────────────────────────────────────────────────

describe('GET /api/signals/:id', () => {
  let app, tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb({ withScanRun: true, withSignals: true });
    app = loadApp(tmpDb);
  });
  afterAll(() => { db._reset(); cleanup(tmpDb); });

  it('returns 200 with signal fields', async () => {
    const res = await request(app).get('/api/signals/1');
    expect(res.status).toBe(200);
    expect(res.body.id).toBe(1);
    expect(res.body.ticker).toBe('AAPL');
  });

  it('gate_detail_json round-trips as parsed array (AC3)', async () => {
    const res = await request(app).get('/api/signals/1');
    const detail = res.body.gate_detail;
    expect(Array.isArray(detail)).toBe(true);
    // Verify the exact values seeded in helpers.js
    expect(detail[0]).toEqual({ name: 'Trend alignment', status: 'pass', detail: 'close > SMA50 > SMA200' });
    expect(detail[2]).toEqual({ name: 'Earnings clear',  status: 'skip', detail: 'no earnings data' });
    expect(detail[4]).toEqual({ name: 'RS line at 60d high', status: 'bonus_pass', detail: '' });
    // Raw JSON field must not be exposed
    expect(res.body).not.toHaveProperty('gate_detail_json');
  });

  it('signal with no gate_detail has empty array', async () => {
    const res = await request(app).get('/api/signals/2');
    expect(res.status).toBe(200);
    expect(res.body.ticker).toBe('MSFT');
    expect(res.body.gate_detail).toEqual([]);
  });

  it('returns 404 for unknown id', async () => {
    const res = await request(app).get('/api/signals/9999');
    expect(res.status).toBe(404);
  });

  it('returns 400 for invalid id', async () => {
    const res = await request(app).get('/api/signals/abc');
    expect(res.status).toBe(400);
  });
});

// ── PATCH /api/signals/:id ───────────────────────────────────────────────────

describe('PATCH /api/signals/:id', () => {
  let app, tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb({ withScanRun: true, withSignals: true });
    app = loadApp(tmpDb);
  });
  afterAll(() => { db._reset(); cleanup(tmpDb); });

  it('dismisses an open signal with a note', async () => {
    const res = await request(app).patch('/api/signals/2')
      .send({ exit_reason: 'dismissed', notes: 'Sector too weak' });
    expect(res.status).toBe(200);
    expect(res.body.exit_reason).toBe('dismissed');
    expect(res.body.notes).toBe('Sector too weak');
    expect(res.body.outcome_checked_at).toBeTruthy();
  });

  it('closes a signal with entry/exit prices and r_multiple', async () => {
    const res = await request(app).patch('/api/signals/1')
      .send({ exit_reason: 'target', entry_px: 181.0, exit_px: 200.0, r_multiple: 0.76 });
    expect(res.status).toBe(200);
    expect(res.body.exit_reason).toBe('target');
    expect(res.body.entry_px).toBeCloseTo(181.0);
    expect(res.body.exit_px).toBeCloseTo(200.0);
    expect(res.body.r_multiple).toBeCloseTo(0.76);
  });

  it('returns 400 for invalid signal id', async () => {
    const res = await request(app).patch('/api/signals/abc').send({ exit_reason: 'dismissed' });
    expect(res.status).toBe(400);
  });

  it('returns 400 when exit_reason is missing', async () => {
    const res = await request(app).patch('/api/signals/1').send({});
    expect(res.status).toBe(400);
  });

  it('returns 400 for unknown exit_reason', async () => {
    const res = await request(app).patch('/api/signals/1').send({ exit_reason: 'garbage' });
    expect(res.status).toBe(400);
  });

  it('returns 404 for unknown signal id', async () => {
    const res = await request(app).patch('/api/signals/9999').send({ exit_reason: 'dismissed' });
    expect(res.status).toBe(404);
  });

  it('returns 503 when DB is missing', async () => {
    const noDbApp = loadApp('/nonexistent/scanner.db');
    const res = await request(noDbApp).patch('/api/signals/1').send({ exit_reason: 'dismissed' });
    expect(res.status).toBe(503);
    db._reset();
  });
});

// ── /api/signals/history ─────────────────────────────────────────────────────

describe('GET /api/signals/history', () => {
  let app, tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb({ withScanRun: true, withSignals: true, withResolved: true });
    app = loadApp(tmpDb);
  });
  afterAll(() => { db._reset(); cleanup(tmpDb); });

  it('returns all live signals by default', async () => {
    const res = await request(app).get('/api/signals/history');
    expect(res.status).toBe(200);
    expect(res.body.count).toBe(2);
  });

  it('filters to open signals', async () => {
    const res = await request(app).get('/api/signals/history?status=open');
    expect(res.status).toBe(200);
    expect(res.body.signals.every(s => s.exit_reason === null)).toBe(true);
    expect(res.body.count).toBe(1); // MSFT is still open
  });

  it('filters to resolved signals', async () => {
    const res = await request(app).get('/api/signals/history?status=resolved');
    expect(res.status).toBe(200);
    expect(res.body.signals.every(s => s.exit_reason !== null)).toBe(true);
    expect(res.body.count).toBe(1); // AAPL resolved
  });

  it('filters by date range', async () => {
    const res = await request(app).get('/api/signals/history?from=2026-06-22&to=2026-06-22');
    expect(res.status).toBe(200);
    expect(res.body.count).toBe(2);
  });

  it('returns 400 for invalid status', async () => {
    const res = await request(app).get('/api/signals/history?status=garbage');
    expect(res.status).toBe(400);
  });
});
