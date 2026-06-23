'use strict';

const request = require('supertest');
const path = require('path');
const fs = require('fs');
const Database = require('better-sqlite3');
const os = require('os');

// Must reset the cached db connection before changing DB_PATH
const db = require('../db');

function makeTmpDb(schemaVersion = 3, withScanRun = true) {
  const tmpFile = path.join(os.tmpdir(), `traderassist_test_${Date.now()}.db`);
  const conn = new Database(tmpFile);

  conn.exec(`
    CREATE TABLE schema_version (version INTEGER NOT NULL);
    CREATE TABLE runs (
      run_id TEXT PRIMARY KEY,
      kind TEXT NOT NULL,
      strategy TEXT,
      universe TEXT,
      params_json TEXT,
      started_at TEXT,
      finished_at TEXT,
      signal_count INTEGER
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
      metrics_json TEXT,
      biases_json TEXT
    );
    INSERT INTO schema_version (version) VALUES (${schemaVersion});
  `);

  if (withScanRun) {
    conn.prepare(
      "INSERT INTO runs (run_id, kind, strategy, started_at, finished_at, signal_count) VALUES (?,?,?,?,?,?)"
    ).run('2026-06-22', 'scan', 'pullback', '2026-06-22T20:00:00', '2026-06-22T20:01:00', 3);
  }

  conn.close();
  return tmpFile;
}

function loadApp(dbPath) {
  // Reset cached connection and set env before requiring app
  db._reset();
  process.env.DB_PATH = dbPath;
  // Re-require app with fresh module cache for routes (db module is already loaded)
  jest.resetModules();
  const freshDb = require('../db');
  freshDb._reset();
  process.env.DB_PATH = dbPath;
  const app = require('../app');
  return app;
}

// ── tests ──────────────────────────────────────────────────────────────────────

describe('GET /api/health — DB present', () => {
  let app;
  let tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb(1, true);
    app = loadApp(tmpDb);
  });

  afterAll(() => {
    db._reset();
    try { fs.unlinkSync(tmpDb); } catch (_) {}
  });

  it('returns 200 with status ok', async () => {
    const res = await request(app).get('/api/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
  });

  it('includes schema_version', async () => {
    const res = await request(app).get('/api/health');
    expect(res.body.schema_version).toBe(1);
  });

  it('includes db_path', async () => {
    const res = await request(app).get('/api/health');
    expect(typeof res.body.db_path).toBe('string');
    expect(res.body.db_path.length).toBeGreaterThan(0);
  });

  it('includes last_scan_run with expected fields', async () => {
    const res = await request(app).get('/api/health');
    const run = res.body.last_scan_run;
    expect(run).not.toBeNull();
    expect(run.run_id).toBe('2026-06-22');
    expect(run.signal_count).toBe(3);
    expect(run.strategy).toBe('pullback');
  });
});

describe('GET /api/health — DB present, no scan runs yet', () => {
  let app;
  let tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb(1, false);
    app = loadApp(tmpDb);
  });

  afterAll(() => {
    db._reset();
    try { fs.unlinkSync(tmpDb); } catch (_) {}
  });

  it('returns 200 with last_scan_run null when no runs exist', async () => {
    const res = await request(app).get('/api/health');
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('ok');
    expect(res.body.last_scan_run).toBeNull();
  });
});

describe('GET /api/health — DB missing', () => {
  let app;

  beforeAll(() => {
    app = loadApp('/nonexistent/path/scanner.db');
  });

  afterAll(() => {
    db._reset();
  });

  it('returns 503', async () => {
    const res = await request(app).get('/api/health');
    expect(res.status).toBe(503);
  });

  it('response includes run-the-scanner message', async () => {
    const res = await request(app).get('/api/health');
    expect(res.body.status).toBe('unavailable');
    expect(res.body.message).toMatch(/run the scanner first/i);
  });

  it('response includes db_path for diagnostics', async () => {
    const res = await request(app).get('/api/health');
    expect(typeof res.body.db_path).toBe('string');
  });
});

describe('CORS headers', () => {
  let app;
  let tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb(1, false);
    app = loadApp(tmpDb);
  });

  afterAll(() => {
    db._reset();
    try { fs.unlinkSync(tmpDb); } catch (_) {}
  });

  it('allows Angular dev origin (localhost:4200)', async () => {
    const res = await request(app)
      .get('/api/health')
      .set('Origin', 'http://localhost:4200');
    expect(res.headers['access-control-allow-origin']).toBe('http://localhost:4200');
  });
});

describe('Unknown routes', () => {
  let app;
  let tmpDb;

  beforeAll(() => {
    tmpDb = makeTmpDb(1, false);
    app = loadApp(tmpDb);
  });

  afterAll(() => {
    db._reset();
    try { fs.unlinkSync(tmpDb); } catch (_) {}
  });

  it('returns 404 for unknown route', async () => {
    const res = await request(app).get('/api/unknown-endpoint');
    expect(res.status).toBe(404);
  });
});
