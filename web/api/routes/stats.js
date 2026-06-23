'use strict';

const { Router } = require('express');
const db = require('../db');

const router = Router();

// GET /api/stats/summary — dashboard counts
router.get('/stats/summary', (req, res) => {
  const stats = db.getSummaryStats();

  if (stats === null) {
    return res.status(503).json({ error: 'Database unavailable' });
  }

  res.json(stats);
});

module.exports = router;
