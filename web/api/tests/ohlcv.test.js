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

describe('GET /api/ohlcv/:ticker', () => {
  let app, tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb({ withBars: true, withSignals: false });
    app = loadApp(tmpDb);
  });
  afterAll(() => { db._reset(); cleanup(tmpDb); });

  it('returns 200 with bars array for a known ticker', async () => {
    const res = await request(app).get('/api/ohlcv/AAPL');
    expect(res.status).toBe(200);
    expect(res.body.ticker).toBe('AAPL');
    expect(Array.isArray(res.body.bars)).toBe(true);
    expect(res.body.count).toBe(5);
  });

  it('bars are in chronological order', async () => {
    const res = await request(app).get('/api/ohlcv/AAPL');
    const dates = res.body.bars.map(b => b.date);
    expect(dates).toEqual([...dates].sort());
  });

  it('each bar has required OHLCV fields', async () => {
    const res = await request(app).get('/api/ohlcv/AAPL');
    const bar = res.body.bars[0];
    ['date', 'open', 'high', 'low', 'close', 'volume'].forEach(f => {
      expect(bar).toHaveProperty(f);
    });
  });

  it('accepts lowercase ticker and upcases it', async () => {
    const res = await request(app).get('/api/ohlcv/aapl');
    expect(res.status).toBe(200);
    expect(res.body.ticker).toBe('AAPL');
  });

  it('returns empty bars array for an unknown ticker', async () => {
    const res = await request(app).get('/api/ohlcv/ZZZZ');
    expect(res.status).toBe(200);
    expect(res.body.count).toBe(0);
    expect(res.body.bars).toEqual([]);
  });

  it('respects the bars query param', async () => {
    const res = await request(app).get('/api/ohlcv/AAPL?bars=2');
    expect(res.status).toBe(200);
    expect(res.body.count).toBe(2);
    expect(res.body.bars.length).toBe(2);
    // Should return the 2 most recent bars
    expect(res.body.bars[1].date).toBe('2026-06-05');
  });

  it('rejects an invalid ticker', async () => {
    const res = await request(app).get('/api/ohlcv/BAD-TICK-ER-LONG');
    expect(res.status).toBe(400);
  });

  it('rejects bars=0', async () => {
    const res = await request(app).get('/api/ohlcv/AAPL?bars=0');
    expect(res.status).toBe(400);
  });

  it('returns 503 when database is unavailable', async () => {
    jest.resetModules();
    const freshDb = require('../db');
    freshDb._reset();
    process.env.DB_PATH = '/nonexistent/path/scanner.db';
    const freshApp = require('../app');
    const res = await request(freshApp).get('/api/ohlcv/AAPL');
    expect(res.status).toBe(503);
    freshDb._reset();
  });
});
