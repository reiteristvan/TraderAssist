---
status: complete
phase: 02-industry-momentum-computation-schema-v7
source: [02-VERIFICATION.md]
started: 2026-07-01T00:00:00Z
updated: 2026-07-01T11:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Live Scan DB Migration + Industry Column Population

**Setup:**
```bash
python scan.py refresh --file universes/sample.txt
python scan.py scan --strategy pullback --file universes/sample.txt
```

**Then query scanner.db:**
```sql
SELECT version FROM schema_version;
SELECT ticker, industry_group, industry_momentum, industry_above_50ma
FROM signals ORDER BY created_at DESC LIMIT 10;
```

expected: |
  schema_version = 9;
  mapped tickers: non-null industry_group (e.g. "Semiconductors") and signed float in industry_momentum;
  any unmapped ticker: SQL NULL (not 0.0) in industry_momentum and industry_group
result: pass

### 2. Backtest Historical Spot-Check (IND-06 Real-Data Confirmation)

**Setup:**
```bash
python scan.py backtest --strategy pullback --file universes/sample.txt \
  --start 2024-01-01 --end 2024-06-30 --out runs/ind_check/
```

Pick a specific signal row for a known-industry ticker on a specific date.
Manually compute: `(ETF.Close[date] / ETF.Close[date-20] - 1) * 100` using real yfinance historical closes.
Compare to `industry_momentum` stored in scanner.db for that row.

expected: |
  Stored industry_momentum matches manually-computed 20-day ROC from actual
  historical ETF closes within floating-point rounding.
  Confirms no future ETF prices consumed (IND-06 real-data validation).
result: pass

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
