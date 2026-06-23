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

describe('GET /api/runs', () => {
  let app, tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb({ withScanRun: true, withBacktest: true });
    app = loadApp(tmpDb);
  });
  afterAll(() => { db._reset(); cleanup(tmpDb); });

  it('returns all runs without filter', async () => {
    const res = await request(app).get('/api/runs');
    expect(res.status).toBe(200);
    expect(res.body.count).toBe(2); // 1 scan + 1 backtest
    expect(Array.isArray(res.body.runs)).toBe(true);
  });

  it('filters by kind=scan', async () => {
    const res = await request(app).get('/api/runs?kind=scan');
    expect(res.status).toBe(200);
    expect(res.body.runs.every(r => r.kind === 'scan')).toBe(true);
    expect(res.body.count).toBe(1);
  });

  it('filters by kind=backtest', async () => {
    const res = await request(app).get('/api/runs?kind=backtest');
    expect(res.status).toBe(200);
    expect(res.body.runs.every(r => r.kind === 'backtest')).toBe(true);
    expect(res.body.count).toBe(1);
  });

  it('returns 400 for invalid kind', async () => {
    const res = await request(app).get('/api/runs?kind=foo');
    expect(res.status).toBe(400);
  });
});

describe('GET /api/runs/:run_id', () => {
  let app, tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb({ withScanRun: true, withBacktest: true });
    app = loadApp(tmpDb);
  });
  afterAll(() => { db._reset(); cleanup(tmpDb); });

  it('returns scan run without metrics', async () => {
    const res = await request(app).get('/api/runs/2026-06-22');
    expect(res.status).toBe(200);
    expect(res.body.run_id).toBe('2026-06-22');
    expect(res.body.kind).toBe('scan');
    expect(res.body).not.toHaveProperty('metrics');
  });

  it('returns backtest run WITH metrics and biases', async () => {
    const res = await request(app).get('/api/runs/bt_2026_pb');
    expect(res.status).toBe(200);
    expect(res.body.kind).toBe('backtest');
    expect(res.body.metrics).toBeDefined();
    expect(res.body.metrics.win_rate).toBeCloseTo(0.54);
    expect(res.body.metrics.expectancy_r).toBeCloseTo(0.38);
    expect(Array.isArray(res.body.biases)).toBe(true);
    expect(res.body.biases.length).toBe(2);
  });

  it('returns score_buckets, conf_buckets, gate_attribution for backtest run', async () => {
    const res = await request(app).get('/api/runs/bt_2026_pb');
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body.score_buckets)).toBe(true);
    expect(res.body.score_buckets.length).toBe(4);
    expect(res.body.score_buckets[1].bucket).toBe('55–69');
    expect(Array.isArray(res.body.conf_buckets)).toBe(true);
    expect(res.body.conf_buckets[2].bucket).toBe('HIGH');
    expect(Array.isArray(res.body.gate_attribution)).toBe(true);
    expect(res.body.gate_attribution[0].gate).toBe('Volume contraction');
  });

  it('returns 404 for unknown run', async () => {
    const res = await request(app).get('/api/runs/nonexistent');
    expect(res.status).toBe(404);
  });
});
