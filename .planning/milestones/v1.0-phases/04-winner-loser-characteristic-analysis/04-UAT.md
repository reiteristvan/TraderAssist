---
status: complete
phase: 04-winner-loser-characteristic-analysis
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md]
started: 2026-07-02T07:50:00+02:00
updated: 2026-07-02T08:00:00+02:00
---

## Current Test

[testing complete]

## Tests

### 1. pytest suite green
expected: Run `pytest -q` in the project root. All 239 tests pass. No failures or errors.
result: pass

### 2. W/L report section in CLI backtest output
expected: |
  Run `python scan.py backtest --strategy pullback --file universes/sp500.txt --start 2022-01-01 --end 2026-01-01 --out runs/wl_test/`
  (or any existing large run). Open `runs/<run>/report.md`. The report contains a section:
  `## Winner/Loser Characteristic Analysis (Pre-registered)` with a table showing 6 rows
  (RSI at entry, RVOL, Pullback depth %, ATR multiple, Industry momentum, Pct to 52w high)
  each with Winners Median and Losers Median columns.
  If <200 qualified trades, report instead shows: `Insufficient data (<200 qualified trades) — analysis not run.`
result: pass

### 3. wl_analysis key in API response
expected: |
  With the API running (`cd web/api && npm start`), call:
  `curl http://localhost:3000/api/runs/<run_id>/report`
  (use a run_id from a backtest run executed AFTER Phase 4 code was merged, i.e., after 2026-07-01 21:00)
  The JSON response includes a `wl_analysis` key. Its value is either null (if <200 trades)
  or an object with `total_qualified`, `aborted`, `strategies` array.
result: pass
note: correct endpoint is /api/runs/<run_id> (not /api/runs/<run_id>/report)

### 4. W/L Analysis cards visible in backtest detail UI
expected: |
  Open http://localhost:4200, navigate to Backtests page, select a run with ≥200 qualified trades
  generated after Phase 4 was merged. The detail panel shows one or more cards headed
  "W/L Analysis — Pullback" (or Breakout). These cards appear between the
  "Target distance — by ATR" card and the trade list.
result: pass

### 5. Cards show exactly 6 metric rows
expected: |
  In the W/L Analysis card for any strategy, the metric table has exactly 6 rows in this order:
  RSI at entry | RVOL | Pullback depth % | ATR multiple | Industry momentum | Pct to 52w high
  Each row shows Winners column, Losers column, and Delta column.
result: pass

### 6. Value formatting is correct
expected: |
  In the W/L metric table, check these format rules:
  - RSI at entry: plain 1 decimal (e.g., "55.1" not "55.1x" or "55.1%")
  - RVOL: 2 decimals + "x" suffix (e.g., "1.23x")
  - Pullback depth %: 1 decimal + "%" (e.g., "8.5%")
  - ATR multiple: 2 decimals, no suffix (e.g., "1.23")
  - Industry momentum: 1 decimal + "%" (e.g., "3.2%")
  - Pct to 52w high: 1 decimal + "%" (e.g., "12.3%")
  - Null/missing values show "—" (em dash)
result: pass

### 7. Delta column has explicit +/- sign
expected: |
  In the W/L Analysis card, the Delta column (Winners − Losers) shows an explicit leading
  sign on every non-null value: positive deltas show "+X.Xx" / "+X.X%" etc.,
  negative deltas show "−X.Xx". Zero shows "+0.0" (or equivalent with sign).
  No delta value is shown without a sign prefix.
result: pass

### 8. Abort warning shown for insufficient-data run
expected: |
  Select a backtest run (after Phase 4) with fewer than 200 qualified trades.
  Instead of strategy cards, the UI shows a warning box containing the abort reason,
  e.g., "Insufficient data: only X qualified trades (minimum 200 required)."
  No metric table or strategy card is rendered.
result: pass

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
