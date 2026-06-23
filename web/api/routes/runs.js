'use strict';

const { Router } = require('express');
const db = require('../db');

const router = Router();

// GET /api/runs?kind=scan|backtest — list of runs
router.get('/runs', (req, res) => {
  const { kind } = req.query;

  if (kind && !['scan', 'backtest'].includes(kind)) {
    return res.status(400).json({ error: 'kind must be "scan" or "backtest"' });
  }

  const runs = db.getRuns(kind || null);

  if (runs === null) {
    return res.status(503).json({ error: 'Database unavailable' });
  }

  res.json({ count: runs.length, runs });
});

// GET /api/runs/:run_id — single run with backtest report if available
router.get('/runs/:run_id', (req, res) => {
  const { run_id } = req.params;

  const run = db.getRunById(run_id);

  if (run === null && db.getDb() === null) {
    return res.status(503).json({ error: 'Database unavailable' });
  }
  if (!run) {
    return res.status(404).json({ error: `Run "${run_id}" not found` });
  }

  const result = Object.assign({}, run);

  if (run.kind === 'backtest') {
    const report = db.getBacktestReport(run_id);
    result.metrics = report ? JSON.parse(report.metrics_json || '{}') : null;
    result.biases  = report ? JSON.parse(report.biases_json  || '[]') : null;
  }

  res.json(result);
});

module.exports = router;
