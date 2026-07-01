---
phase: 02-industry-momentum-computation-schema-v7
plan: "02"
subsystem: scanner/core, scanner/simulate, scanner/backtest, scanner/journal
tags: [industry-momentum, rank-percentile, no-lookahead, tdd, backtest]
dependency_graph:
  requires: [02-01-PLAN.md]
  provides: [_attach_industry_rank_pct(), industry_rank_pct-live, industry-fields-backtest]
  affects: [scanner/core.py, scanner/simulate.py, scanner/backtest.py, scanner/journal.py, tests/test_core.py]
tech_stack:
  added: []
  patterns: [pandas.Series.rank(pct=True) post-loop batch, per-day ETF momentum dict before ticker sub-loop, Optional dataclass fields with None defaults]
key_files:
  created: []
  modified:
    - scanner/core.py
    - scanner/simulate.py
    - scanner/backtest.py
    - scanner/journal.py
    - tests/test_core.py
decisions:
  - _attach_industry_rank_pct is a named helper in core.py (testable directly) called from run_scan post-loop
  - per-day ETF momentum dict + day_rank computed before ticker sub-loop in generate_signals (Pitfall 3 prevention)
  - day_ind_cache dict avoids calling _industry_strength twice per ticker per day
  - pandas import inside the backtest day-loop uses alias _pd to avoid shadowing module-level pd
  - Signal fields appended last with None defaults — all positional callsites unaffected
metrics:
  duration: "~15 minutes"
  completed: "2026-07-01"
  tasks_completed: 3
  files_modified: 4
status: complete
---

# Phase 02 Plan 02: Industry Rank Percentile + Backtest Industry Wiring Summary

**One-liner:** Post-loop `_attach_industry_rank_pct` assigns within-run ETF rank percentile to live signals; `generate_signals` computes per-day ETF momentum from `sliced_market` and attaches all four industry fields to each `Signal` with no look-ahead.

## What Was Built

### `scanner/core.py` — `_attach_industry_rank_pct()`

New helper placed adjacent to `_industry_strength()`. Accepts a `list[dict]` of assembled rows (mutates in-place). Algorithm:
- Collects one momentum score per distinct ETF (first-occurrence wins)
- If fewer than 2 distinct ETFs: returns without setting any value (all rows keep `industry_rank_pct = None`)
- Otherwise: `pd.Series(etf_scores).rank(pct=True)` (ascending) → higher momentum = higher percentile
- NaN results coerced to `None` before assignment (T-02-06 mitigation)

Called from `run_scan()` as a post-loop step after all rows are assembled, before `pd.DataFrame(rows)`.

### `scanner/simulate.py` — `Signal` dataclass extension

Four fields appended after `close: float = 0.0`, all with `Optional[X] = None` defaults:
- `industry_group: Optional[str] = None`
- `industry_momentum: Optional[float] = None`
- `industry_above_50ma: Optional[bool] = None`
- `industry_rank_pct: Optional[float] = None`

All existing positional `Signal(...)` constructions remain valid.

### `scanner/backtest.py` — per-day industry momentum + rank

Imports `_industry_strength` and `_attach_industry_rank_pct` from `scanner.core`.

Before the ticker sub-loop for each day:
- Builds `day_etf_scores` dict: one momentum score per distinct ETF resolved from `quality_by_ticker` via `_industry_strength(..., sliced_market)` — strictly `sliced_market` (index <= as_of), never `full_market` (IND-06)
- Caches per-ticker strength results in `day_ind_cache` to avoid duplicate calls
- Computes `day_rank = pd.Series(day_etf_scores).rank(pct=True)` when >= 2 ETFs; empty Series otherwise

In the ticker body, `Signal(...)` now passes:
- `industry_group=getattr(_q_sig, "industry", None)`
- `industry_momentum=_strength.get("industry_mom_20d")`
- `industry_above_50ma=_strength.get("industry_above_50ma")`
- `industry_rank_pct=float(day_rank[_etf])` or `None`

### `scanner/journal.py` — backtest sig dict

The `source="backtest"` sig dict builder now includes four new keys read directly from the `Signal` object:
- `"industry_group": s.industry_group`
- `"industry_momentum": s.industry_momentum`
- `"industry_above_50ma": s.industry_above_50ma`
- `"industry_rank_pct": s.industry_rank_pct`

These flow to `insert_signals_batch()` and are persisted in the DB.

## Task Execution

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add failing tests (RED) | `df0c6c8` | tests/test_core.py |
| 2 | _attach_industry_rank_pct + Signal fields (GREEN) | `5be0809` | scanner/core.py, scanner/simulate.py |
| 3 | Backtest + journal wiring (GREEN) | `bef5aa1` | scanner/backtest.py, scanner/journal.py |

## Test Results

Full suite: **230 tests, all passing** (offline).

New tests added:
- `test_industry_rank_pct_multi_etf` — 3 rows, 3 ETFs; top ETF gets rank 1.0; rank is ascending
- `test_industry_rank_pct_single_etf_returns_none` — all rows same ETF; industry_rank_pct stays None
- `test_industry_no_lookahead_backtest` — post-as_of spike changes momentum when full_market used; Signal correctly stores sliced-market value

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as specified. The `day_ind_cache` optimisation (caching `_industry_strength` results per ticker per day to avoid duplicate calls) is a performance improvement that does not change correctness.

## Known Stubs

None. All four industry fields are fully populated in both the live scan and backtest paths.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced.

T-02-04 (look-ahead bias): mitigated — all ETF reads in `generate_signals` use `sliced_market` (df[df.index <= as_of_ts]); automated test asserts post-as_of spike is ignored.

T-02-05 (rank on partial set): mitigated — rank is a post-loop / pre-sub-loop batch step over all distinct ETFs; single-ETF case returns None; unit tests assert correct ascending ranks.

T-02-06 (NaN coercion): mitigated — NaN values coerced to Python `None` in both `_attach_industry_rank_pct` and the `_rank_pct` assignment in backtest.py before assignment.

## Human Verification Required (IND-06 spot-check)

Run the backtest against a small date range, then journal-ingest and query a signal on a specific historical date. Confirm the stored `industry_momentum` matches `(ETF.Close[d] / ETF.Close[d-20] - 1) * 100` using real yfinance historical closes for that exact date:

```bash
python scan.py backtest --strategy pullback --file universes/sample.txt \
  --start 2024-01-01 --end 2024-06-30 --out runs/ind_check/
python scan.py journal ingest runs/ind_check/
# Then query scanner.db:
# SELECT ticker, date, industry_group, industry_momentum, industry_rank_pct
#   FROM signals WHERE source='backtest' ORDER BY date LIMIT 20
```

## Self-Check: PASSED

- scanner/core.py: FOUND
- scanner/simulate.py: FOUND
- scanner/backtest.py: FOUND
- scanner/journal.py: FOUND
- tests/test_core.py: FOUND
- commit df0c6c8 (RED tests): FOUND
- commit 5be0809 (GREEN core+simulate): FOUND
- commit bef5aa1 (GREEN backtest+journal): FOUND
