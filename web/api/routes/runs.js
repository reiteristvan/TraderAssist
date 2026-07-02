'use strict';

const { Router } = require('express');
const db = require('../db');

const router = Router();

function safeParse(json, fallback) {
  try { return JSON.parse(json || JSON.stringify(fallback)); } catch { return fallback; }
}

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
    if (report) {
      const reportData = safeParse(report.metrics_json, {});
      // Support both old flat format and new nested format (full json_data from render_report)
      if (reportData.metrics) {
        result.metrics            = reportData.metrics;
        result.score_buckets      = reportData.score_buckets      || [];
        result.conf_buckets       = reportData.conf_buckets       || [];
        result.gate_attribution   = reportData.gate_attribution   || [];
        result.monthly_signals    = reportData.monthly_signals    || {};
        result.trades             = reportData.trades             || [];
        result.failure_analysis   = reportData.failure_analysis    || null;
        result.stop_out_forensics = reportData.stop_out_forensics  || null;
        result.target_r_buckets   = reportData.target_r_buckets    || [];
        result.target_atr_buckets = reportData.target_atr_buckets  || [];
        result.wl_analysis        = reportData.wl_analysis         || null;
      } else {
        result.metrics = reportData;
      }
      result.biases = safeParse(report.biases_json, []);
    } else {
      result.metrics = null;
      result.biases  = null;
    }
  }

  res.json(result);
});

module.exports = router;
