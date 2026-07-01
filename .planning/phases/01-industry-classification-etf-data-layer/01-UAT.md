---
status: testing
phase: 01-industry-classification-etf-data-layer
source: [01-VERIFICATION.md]
started: "2026-07-01T00:00:00Z"
updated: "2026-07-01T00:00:00Z"
---

## Current Test

number: 1
name: Industry ETF Parquet Cache — Network Validation (SC2)
expected: |
  All 17 new ETF tickers produce .parquet files under data/ohlcv/ with no download errors.
awaiting: user response

## Tests

### 1. Industry ETF Parquet Cache — Network Validation (SC2)

**Command:** `python scan.py refresh --file universes/sample.txt`

**Expected:** All 17 new ETF tickers (XSD, XSW, XBI, XPH, XHE, XHS, KRE, KBE, KIE, KCE, XHB, XRT, XAR, XOP, XES, GDX, XME) produce `.parquet` files under `data/ohlcv/` with no "Empty response" or retry-exhausted errors logged.

result: [pending]

---

### 2. Live industryKey Mapping Coverage — yfinance API Validation (SC1)

**Command:** `python scan.py scan --strategy pullback --ticker AAPL` (repeat for ~9 more tickers across sectors)

**Suggested tickers:** AAPL, MSFT, JPM, UNH, AMZN, LMT, XOM, NEM, DHI, plus one regional bank (e.g. FITB or RF)

**Expected:** For each ticker, `QualityInfo.industry_key` returns a non-null slug (e.g. `semiconductors`, `software-infrastructure`, `banks-diversified`) that appears as a key in `INDUSTRY_ETF_MAP`. At minimum 8 of 10 tickers should resolve to a direct INDUSTRY_ETF_MAP entry.

result: [pending]

---

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
