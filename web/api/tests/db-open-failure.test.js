'use strict';

/**
 * Proves the D2/D-02 diagnostics fix: getDb() and getWriteDb() log the
 * caught open error via console.error (prefixed "[db]") before returning
 * null, while the legitimate absent-file path stays silent. The 503 HTTP
 * contract must stay byte-identical — only a server-console line is added.
 *
 * Failure trigger: pointing DB_PATH at an existing DIRECTORY passes the
 * fs.existsSync guard and makes the `new Database(...)` constructor throw
 * SQLITE_CANTOPEN_ISDIR — verified during planning under better-sqlite3
 * 12.6.2 / Node 24. A garbage-bytes file does NOT throw from the
 * constructor (SQLITE_NOTADB only surfaces at first query), so it is not
 * usable as the trigger here.
 */

const request = require('supertest');
const fs = require('fs');
const os = require('os');
const path = require('path');

describe('db open-failure diagnostics (getDb / getWriteDb)', () => {
  let db;
  let tmpDir;
  let nonexistentPath;
  let consoleErrorSpy;
  const savedDbPath = process.env.DB_PATH;

  beforeEach(() => {
    jest.resetModules();
    db = require('../db');
    db._reset();
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'traderassist_db_open_failure_'));
    nonexistentPath = path.join(tmpDir, 'does-not-exist.db');
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    db._reset();
    consoleErrorSpy.mockRestore();
    if (savedDbPath === undefined) {
      delete process.env.DB_PATH;
    } else {
      process.env.DB_PATH = savedDbPath;
    }
    try { fs.rmdirSync(tmpDir); } catch (_) {}
  });

  it('Test 1: getDb() logs [db]-prefixed error and returns null when DB_PATH is a directory', () => {
    process.env.DB_PATH = tmpDir;
    const result = db.getDb();

    expect(result).toBeNull();
    const dbCalls = consoleErrorSpy.mock.calls.filter(
      (args) => typeof args[0] === 'string' && args[0].includes('[db]')
    );
    expect(dbCalls.length).toBeGreaterThan(0);
    const [message, err] = dbCalls[0];
    expect(message).toContain('getDb');
    expect(message).toContain(path.resolve(tmpDir));
    // Not `toBeInstanceOf(Error)`: better-sqlite3's native SqliteError is bound
    // to whichever test file's VM realm first dlopen'd the addon (a process-wide
    // native binding cache), so cross-realm `instanceof` is unreliable under
    // Jest's per-file sandboxing. Assert on error shape instead.
    expect(typeof err.message).toBe('string');
    expect(err.message.length).toBeGreaterThan(0);
  });

  it('Test 2: enqueueJob() (getWriteDb() path) logs [db]-prefixed error and returns null when DB_PATH is a directory', () => {
    process.env.DB_PATH = tmpDir;
    const result = db.enqueueJob('diagnose', {});

    expect(result).toBeNull();
    const dbCalls = consoleErrorSpy.mock.calls.filter(
      (args) => typeof args[0] === 'string' && args[0].includes('[db]')
    );
    expect(dbCalls.length).toBeGreaterThan(0);
    const [message, err] = dbCalls[0];
    expect(message).toContain('getWriteDb');
    expect(message).toContain(path.resolve(tmpDir));
    expect(typeof err.message).toBe('string');
    expect(err.message.length).toBeGreaterThan(0);
  });

  it('Test 3 (quiet path): getDb() logs nothing when DB_PATH points at a non-existent file', () => {
    process.env.DB_PATH = nonexistentPath;
    const result = db.getDb();

    expect(result).toBeNull();
    const dbCalls = consoleErrorSpy.mock.calls.filter(
      (args) => typeof args[0] === 'string' && args[0].includes('[db]')
    );
    expect(dbCalls.length).toBe(0);
  });

  it('Test 4 (quiet path, write side): enqueueJob() logs nothing when DB_PATH points at a non-existent file', () => {
    process.env.DB_PATH = nonexistentPath;
    const result = db.enqueueJob('diagnose', {});

    expect(result).toBeNull();
    const dbCalls = consoleErrorSpy.mock.calls.filter(
      (args) => typeof args[0] === 'string' && args[0].includes('[db]')
    );
    expect(dbCalls.length).toBe(0);
  });

  it('Test 5 (contract): GET /api/health still returns the unchanged 503 body when DB_PATH is a directory', async () => {
    process.env.DB_PATH = tmpDir;
    db._reset();
    const app = require('../app');

    const res = await request(app).get('/api/health');

    expect(res.status).toBe(503);
    expect(res.body.status).toBe('unavailable');
    expect(res.body.message).toMatch(/run the scanner first/i);
    expect(typeof res.body.db_path).toBe('string');
  });
});
