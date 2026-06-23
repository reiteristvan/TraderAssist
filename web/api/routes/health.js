'use strict';

const { Router } = require('express');
const db = require('../db');

const router = Router();

router.get('/health', (req, res) => {
  const schemaVersion = db.getSchemaVersion();

  if (schemaVersion === null) {
    return res.status(503).json({
      status: 'unavailable',
      message: 'Database not found — run the scanner first (scan.py scan ...)',
      db_path: db.getDbPath(),
    });
  }

  const lastRun = db.getLastScanRun();

  res.json({
    status: 'ok',
    db_path: db.getDbPath(),
    schema_version: schemaVersion,
    last_scan_run: lastRun
      ? {
          run_id: lastRun.run_id,
          started_at: lastRun.started_at,
          finished_at: lastRun.finished_at,
          signal_count: lastRun.signal_count,
          strategy: lastRun.strategy,
        }
      : null,
  });
});

module.exports = router;
