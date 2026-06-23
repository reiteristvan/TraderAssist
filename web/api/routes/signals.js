'use strict';

const { Router } = require('express');
const db = require('../db');

const router = Router();

// GET /api/signals/latest — most recent live scan's qualified signals
router.get('/signals/latest', (req, res) => {
  const signals = db.getLatestSignals({
    strategy: req.query.strategy || null,
    minScore: req.query.min_score != null ? Number(req.query.min_score) : null,
    confidence: req.query.confidence || null,
  });

  if (signals === null) {
    return res.status(503).json({ error: 'Database unavailable' });
  }

  res.json({ count: signals.length, signals });
});

// GET /api/signals/history — journal list of live signals
router.get('/signals/history', (req, res) => {
  const { from, to, status, strategy } = req.query;

  if (status && !['open', 'resolved'].includes(status)) {
    return res.status(400).json({ error: 'status must be "open" or "resolved"' });
  }

  const signals = db.getSignalHistory({ from, to, status, strategy });

  if (signals === null) {
    return res.status(503).json({ error: 'Database unavailable' });
  }

  res.json({ count: signals.length, signals });
});

// GET /api/signals/:id — single signal with full gate log
router.get('/signals/:id', (req, res) => {
  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid signal id' });
  }

  const signal = db.getSignalById(id);

  if (signal === null && db.getDb() === null) {
    return res.status(503).json({ error: 'Database unavailable' });
  }
  if (!signal) {
    return res.status(404).json({ error: `Signal ${id} not found` });
  }

  res.json(signal);
});

module.exports = router;
