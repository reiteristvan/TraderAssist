'use strict';

const { Router } = require('express');
const db = require('../db');

const router = Router();

// GET /api/ohlcv/:ticker?bars=120
// Returns the most recent OHLCV bars for a ticker (from the bars snapshot table).
router.get('/ohlcv/:ticker', (req, res) => {
  const ticker = req.params.ticker.toUpperCase();
  if (!/^[A-Z]{1,5}(-[A-Z]{1,2})?$/.test(ticker)) {
    return res.status(400).json({ error: 'Invalid ticker format' });
  }

  const limit = req.query.bars != null ? Number(req.query.bars) : 120;
  if (!Number.isInteger(limit) || limit < 1 || limit > 500) {
    return res.status(400).json({ error: 'bars must be an integer 1–500' });
  }

  const bars = db.getOhlcv(ticker, limit);
  if (bars === null) {
    return res.status(503).json({ error: 'Database unavailable' });
  }

  res.json({ ticker, count: bars.length, bars });
});

module.exports = router;
