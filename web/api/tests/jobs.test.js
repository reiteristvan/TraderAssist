'use strict';

const request = require('supertest');
const app = require('../app');
const db = require('../db');
const { makeTmpDb, cleanup } = require('./helpers');

let tmpFile;

beforeEach(() => {
  tmpFile = makeTmpDb({ withScanRun: true });
  process.env.DB_PATH = tmpFile;
  db._reset();
});

afterEach(() => {
  db._reset();
  cleanup(tmpFile);
  delete process.env.DB_PATH;
});

describe('POST /api/jobs', () => {
  it('creates a queued diagnose job and returns id + status', async () => {
    const res = await request(app)
      .post('/api/jobs')
      .send({ kind: 'diagnose', params: { ticker: 'AAPL', strategy: 'pullback' } });

    expect(res.status).toBe(201);
    expect(res.body.id).toBeGreaterThan(0);
    expect(res.body.status).toBe('queued');
  });

  it('returns 400 for unknown kind', async () => {
    const res = await request(app)
      .post('/api/jobs')
      .send({ kind: 'bad_kind', params: {} });

    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/Invalid job kind/);
  });

  it('returns 400 when kind is missing', async () => {
    const res = await request(app)
      .post('/api/jobs')
      .send({ params: { ticker: 'AAPL' } });

    expect(res.status).toBe(400);
  });

  it('returns 503 when DB is missing', async () => {
    db._reset();
    process.env.DB_PATH = '/nonexistent/scanner.db';
    const res = await request(app)
      .post('/api/jobs')
      .send({ kind: 'diagnose', params: { ticker: 'AAPL' } });

    expect(res.status).toBe(503);
  });
});

describe('GET /api/jobs/:id', () => {
  it('returns a job by id after enqueuing', async () => {
    // Enqueue via POST
    const postRes = await request(app)
      .post('/api/jobs')
      .send({ kind: 'diagnose', params: { ticker: 'MSFT', strategy: 'pullback' } });
    expect(postRes.status).toBe(201);
    const jobId = postRes.body.id;

    // Reset so GET uses read connection (picks up the newly written row)
    db._reset();
    process.env.DB_PATH = tmpFile;

    const res = await request(app).get(`/api/jobs/${jobId}`);
    expect(res.status).toBe(200);
    expect(res.body.id).toBe(jobId);
    expect(res.body.kind).toBe('diagnose');
    expect(res.body.status).toBe('queued');
    expect(res.body.params).toEqual({ ticker: 'MSFT', strategy: 'pullback' });
    expect(res.body.params_json).toBeUndefined();
  });

  it('returns 404 for unknown job id', async () => {
    const res = await request(app).get('/api/jobs/99999');
    expect(res.status).toBe(404);
  });

  it('returns 400 for non-numeric id', async () => {
    const res = await request(app).get('/api/jobs/abc');
    expect(res.status).toBe(400);
  });

  it('returns 503 when DB is missing', async () => {
    db._reset();
    process.env.DB_PATH = '/nonexistent/scanner.db';
    const res = await request(app).get('/api/jobs/1');
    expect(res.status).toBe(503);
  });
});
