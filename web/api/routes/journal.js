'use strict';

const { Router } = require('express');
const db = require('../db');

const router = Router();

// GET /api/journal/compare?backtest_run=<run_id> — live vs backtest calibration
router.get('/journal/compare', (req, res) => {
  const runId = req.query.backtest_run;

  if (!runId) {
    return res.status(400).json({ error: 'backtest_run query param is required' });
  }

  const result = db.getJournalCompare(runId);

  if (result === null && db.getDb() === null) {
    return res.status(503).json({ error: 'Database unavailable' });
  }
  if (result === null) {
    return res.status(404).json({ error: `Backtest run "${runId}" not found` });
  }

  res.json(result);
});

module.exports = router;
