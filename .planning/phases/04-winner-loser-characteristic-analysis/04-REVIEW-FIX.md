---
phase: "04"
status: all_fixed
findings_in_scope: 11
fixed: 11
skipped: 0
iteration: 1
---

# Code Review Fix Report — Phase 04

## Summary

All 11 Critical + Warning findings from `04-REVIEW.md` resolved in 3 atomic commits.

## Fixes Applied

### CR-01 — `web/api/routes/runs.js` — Unguarded JSON.parse (FIXED)
Added `safeParse(json, fallback)` helper; replaced both `JSON.parse` calls on `metrics_json` and `biases_json`.
Commit: `b11111d`

### CR-02 — `scanner/report.py:778` — 2-tuple signal key (FIXED)
Changed `sig_by_key` from `(date, ticker)` to `(date, ticker, strategy)` and updated the lookup accordingly.
Commit: `015074e`

### WR-01 — `scanner/backtest.py:374,423` — Bare `except Exception: pass` (FIXED)
Narrowed to `except (ValueError, AttributeError, KeyError, IndexError): pass` in both try/except blocks.
Commit: `28c2bbc`

### WR-02 — `scanner/backtest.py:337` — Import inside per-day loop (FIXED)
Removed `import pandas as _pd` from inside the loop; replaced `_pd.*` usages with the existing top-level `pd` alias.
Commit: `28c2bbc`

### WR-03 — `scanner/backtest.py:406` — `bool(NaN) = True` in MACD (FIXED)
Added `pd.isna` guard: `macd_val = bool(_macd_raw) if not pd.isna(_macd_raw) else False`.
Commit: `28c2bbc`

### WR-04 — `backtests.component.ts:31-37` — selectRun race condition (FIXED)
Replaced direct `.subscribe()` with `Subject<string>` + `switchMap` pipeline (with `takeUntil(destroy$)` for cleanup).
Commit: `287d640`

### WR-05 — `backtests.component.ts:34-37` — Silent API failure (FIXED)
Added `error:` handler in the switchMap subscription that sets `loadError` message and clears `detailLoading`.
Commit: `287d640`

### WR-06 — `scanner/report.py:734` — Delta column uses value formatter (FIXED)
Added `_fmt_wl_delta()` function (mirrors Angular `fmtWlDelta` with explicit `+/-` signs); delta column now calls `_fmt_wl_delta` instead of `_fmt_wl_value`.
Commit: `015074e`

### WR-07 — `scanner/report.py:239` — Upper-median for even lists (FIXED)
Fixed `median_hold` to average the two middle values for even-length lists (matches `_safe_median` logic).
Commit: `015074e`

### WR-08 — `scanner/backtest.py:435` — Fragile vol_ratio check (FIXED)
Replaced `getattr(result, 'vol_ratio', None) is not None` with `isinstance(result, BreakoutResult)`. Added `from scanner.strategies.breakout import BreakoutResult` import alongside the existing PullbackResult import.
Commit: `28c2bbc`

### WR-09 — `scanner/report.py:759-763` — Wrong earn_skip description (FIXED)
Corrected label from "had no earnings data" to "failed the earnings-proximity gate (earnings within 7 days of entry)".
Commit: `015074e`

## Post-Fix Verification

- `pytest -q`: 239 passed
- `npm test` (API): 71 passed
- `ng test --watch=false`: 37 passed
