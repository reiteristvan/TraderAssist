'use strict';

const express = require('express');
const db = require('../db');

const router = express.Router();

const VALID_KINDS = ['diagnose', 'backtest'];

// POST /api/jobs — enqueue a job
router.post('/', (req, res) => {
  const { kind, params } = req.body || {};

  if (!kind || !VALID_KINDS.includes(kind)) {
    return res.status(400).json({
      error: `Invalid job kind. Must be one of: ${VALID_KINDS.join(', ')}`,
    });
  }

  const result = db.enqueueJob(kind, params || {});
  if (!result) {
    return res.status(503).json({
      error: 'Database unavailable — run the scanner first to initialise the DB.',
    });
  }

  return res.status(201).json(result);
});

// GET /api/jobs/:id — poll job status
router.get('/:id', (req, res) => {
  const id = parseInt(req.params.id, 10);
  if (isNaN(id)) {
    return res.status(400).json({ error: 'Invalid job id' });
  }

  const job = db.getJob(id);
  if (!job) {
    if (!db.getDb()) {
      return res.status(503).json({
        error: 'Database unavailable — run the scanner first to initialise the DB.',
      });
    }
    return res.status(404).json({ error: `Job ${id} not found` });
  }

  // Parse params_json for the response
  const out = Object.assign({}, job);
  if (out.params_json) {
    try { out.params = JSON.parse(out.params_json); }
    catch (_) { out.params = {}; }
    delete out.params_json;
  } else {
    out.params = {};
  }

  return res.json(out);
});

module.exports = router;
