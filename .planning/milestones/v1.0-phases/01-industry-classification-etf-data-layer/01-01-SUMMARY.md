---
phase: 01-industry-classification-etf-data-layer
plan: "01"
subsystem: scanner/core + scanner/data_store
tags: [industry-etf, data-layer, tdd, offline]
status: complete

dependency_graph:
  requires: []
  provides:
    - INDUSTRY_ETF_MAP (scanner/core.py)
    - resolve_industry_etf() (scanner/core.py)
    - extended _MARKET_SYMBOLS (scanner/data_store.py)
  affects:
    - Plan 01-02 (momentum computation consumes resolve_industry_etf and cached ETF frames)

tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN cycle (test before implementation)
    - Two-step ETF resolution chain (industry map -> sector map -> None)
    - Late import in test functions to isolate RED phase from existing tests

key_files:
  created: []
  modified:
    - scanner/core.py
    - scanner/data_store.py
    - tests/test_core.py

decisions:
  - INDUSTRY_ETF_MAP contains explicit sector-fallback entries (e.g. oil-gas-integrated->XLE) rather than a separate fallback table (D-03)
  - resolve_industry_etf returns None immediately when industry_key is None — no sector fallback (D-06)
  - _MARKET_SYMBOLS extended literally (no circular import from data_store into core)

metrics:
  duration_minutes: 3
  completed_date: "2026-07-01"
  tasks_completed: 2
  files_modified: 3
---

# Phase 01 Plan 01: Industry ETF Data Layer Summary

**One-liner:** Industry ETF resolution map (33 keys, 19 ETFs) with two-step lookup chain and deduplicated _MARKET_SYMBOLS extension for Parquet caching.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Add failing resolver tests | f122298 | tests/test_core.py |
| 1 (GREEN) | INDUSTRY_ETF_MAP + resolve_industry_etf | a265962 | scanner/core.py |
| 2 | Extend _MARKET_SYMBOLS | c38d02c | scanner/data_store.py |

## What Was Built

**INDUSTRY_ETF_MAP** (`scanner/core.py`, after `SECTOR_ETF_MAP`):
- 33 industryKey slug entries mapped to 19 unique ETF tickers
- Covers: Technology (5), Healthcare (7), Financial Services (7), Consumer Cyclical (4), Industrials (1), Energy (4), Basic Materials (5)
- Sector-level fallback entries encoded as explicit map entries per D-03: `oil-gas-integrated`→XLE, `oil-gas-midstream`→XLE, `specialty-chemicals`→XLB

**resolve_industry_etf(industry_key, sector)** (`scanner/core.py`):
- Two-step D-07 chain: INDUSTRY_ETF_MAP.get(key) → SECTOR_ETF_MAP.get(sector) → None
- D-06 short-circuit: industry_key=None returns None immediately (no sector fallback)
- Module-level function, importable via `from scanner.core import resolve_industry_etf`

**Extended _MARKET_SYMBOLS** (`scanner/data_store.py`):
- 29 symbols total (12 original + 17 new industry ETFs)
- New: XSD, XSW, XBI, XPH, XHE, XHS, KRE, KBE, KIE, KCE, XHB, XRT, XAR, XOP, XES, GDX, XME
- XLE and XLB already present as sector ETFs; not duplicated (D-02)
- No import of core into data_store (tickers listed literally to avoid circular import)

## Verification

- `pytest tests/test_core.py -k resolve_industry_etf -q`: 6 passed
- `python -m pytest -q`: 217 passed (211 baseline + 6 new resolver tests)
- `tests/test_data_store.py`: 11 passed (list-driven market-data tests self-adapt to 29-symbol list)
- INDUSTRY_ETF_MAP key count: 33 (>= 30 required)
- _MARKET_SYMBOLS duplicate check: 29 == len(set) confirmed

## Human-Check Pending

Per plan Task 2 `<human-check>`: run `python scan.py refresh --file universes/sample.txt` after network is available and confirm all 17 new industry ETF Parquet files appear under `data/ohlcv/` (e.g. XSD.parquet, XBI.parquet, KRE.parquet) with no download errors. This is a network-dependent end-of-phase verification.

## Deviations from Plan

None — plan executed exactly as written. TDD RED/GREEN cycle followed. Late import pattern used in test functions to prevent RED phase from breaking existing test_core.py tests (12 existing tests remained green during RED phase).

## Known Stubs

None — this plan adds data infrastructure only (map, helper, symbol list). No UI rendering, no DB writes, no computed values.

## Threat Surface Scan

No new network endpoints or auth paths introduced. The only new trust boundary crossing is the 17 additional ETF tickers added to _MARKET_SYMBOLS, which the existing fetch_with_retry + _MIN_ROWS guard handles identically to the existing sector ETFs (T-01-01 in plan threat register, disposition: mitigate via existing controls).

## Self-Check: PASSED

- scanner/core.py: FOUND
- scanner/data_store.py: FOUND
- tests/test_core.py: FOUND
- 01-01-SUMMARY.md: FOUND
- Commit f122298 (RED): FOUND
- Commit a265962 (GREEN): FOUND
- Commit c38d02c (Task 2): FOUND
- Full test suite: 217 passed
