'use strict';

require('dotenv').config();

const express = require('express');
const cors = require('cors');

const healthRouter  = require('./routes/health');
const signalsRouter = require('./routes/signals');
const runsRouter    = require('./routes/runs');
const journalRouter = require('./routes/journal');
const statsRouter   = require('./routes/stats');
const jobsRouter    = require('./routes/jobs');
const ohlcvRouter   = require('./routes/ohlcv');

const app = express();

app.use(cors({ origin: 'http://localhost:4200' }));
app.use(express.json());

app.use('/api', healthRouter);
app.use('/api', signalsRouter);
app.use('/api', runsRouter);
app.use('/api', journalRouter);
app.use('/api', statsRouter);
app.use('/api/jobs', jobsRouter);
app.use('/api', ohlcvRouter);

// 404 fallback
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

module.exports = app;
