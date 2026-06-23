'use strict';

require('dotenv').config();

const express = require('express');
const cors = require('cors');

const healthRouter = require('./routes/health');

const app = express();

app.use(cors({ origin: 'http://localhost:4200' }));
app.use(express.json());

app.use('/api', healthRouter);

// 404 fallback
app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

module.exports = app;
