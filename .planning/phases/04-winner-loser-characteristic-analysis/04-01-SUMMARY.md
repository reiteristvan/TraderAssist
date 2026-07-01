---
phase: 04-winner-loser-characteristic-analysis
plan: "01"
subsystem: scanner-engine
tags: [wl-analysis, backtest, report, metrics, anti-cherry-picking]
dependency_graph:
  requires: [02-02-SUMMARY.md]  # Phase 2 industry momentum fields on Signal
  provides: [wl_analysis key in backtest_reports.metrics_json, WL_FEATURES constant in report.py]
  affects: [scanner/simulate.py, scanner/backtest.py, scanner/report.py, tests/test_report.py]
tech_stack:
  added: []
  patterns:
    - getattr() polymorphic field access (no isinstance branching across strategy result types)
    - sorted-list midpoint median (_safe_median)
    - 3-tuple signal lookup key (date, ticker, strategy) in wl_characteristic_analysis
key_files:
  created: []
  modified:
    - scanner/simulate.py
    - scanner/backtest.py
    - scanner/report.py
    - tests/test_report.py
decisions:
  - WL_FEATURES committed to source code before any backtest results viewed — satisfies WLA-06 anti-cherry-picking guard
  - ATR multiple sourced from Trade.target_atr directly (no Signal lookup required)
  - Breakout pct_to_52w_high converted from ratio form (close/high*100) to distance form (100-ratio)
  - pct_to_52w_high detection via getattr(result,'vol_ratio',None) is not None proxy — avoids isinstance + import cycle
  - 3-tuple key (str(date), ticker, strategy) used in wl sig_by_key to support mixed-strategy runs
metrics:
  duration: 4m
  completed_date: "2026-07-01"
  tasks_completed: 3
  files_modified: 4
status: complete
---

# Phase 04 Plan 01: W/L Characteristic Analysis Backend Summary

Delivered the complete Python backend vertical slice for the pre-registered winner/loser characteristic analysis: 4 new Signal fields, backtest metric capture, report.py analysis + render functions, and 8 regression tests covering all WLA requirements.

## What Was Built

### scanner/simulate.py
- `Signal.rsi_entry: Optional[float] = None`
- `Signal.rvol: Optional[float] = None`
- `Signal.pullback_depth_pct: Optional[float] = None`  (None for breakout signals)
- `Signal.pct_to_52w_high: Optional[float] = None`
- All trailing-field — zero impact on positional callers; no DB schema change

### scanner/backtest.py
- `generate_signals()` metric-capture block inserted before `signals.append()`
- Uses `getattr()` polymorphism throughout — no isinstance checks, no import cycles
- Breakout: vol_ratio read directly; pct_to_52w_high converted from ratio to distance form
- Pullback: rvol computed from `precomp_t.vol_sma50`; pct_to_52w_high from `precomp_t.high_52w`
- All precomp reads guarded by `precomp_t is not None` + NaN/zero-denominator checks

### scanner/report.py
- `WL_FEATURES = ['RSI at entry','RVOL','Pullback depth %','ATR multiple','Industry momentum','Pct to 52w high']`
- `WL_MIN_TOTAL = 200`, `WL_MIN_BUCKET = 50`
- `_safe_median(values)` — sorted-list midpoint, None-skipping
- `_extract_wl_metric(metric, trades, sig_by_key)` — per-metric extraction; ATR reads Trade direct
- `wl_characteristic_analysis(signals, qualified_trades)` — abort guard < 200, bucket suppression < 50, 6-row strategy tables
- `_fmt_wl_value(metric, v)` — per-metric formatting matching UI-SPEC Format Rules
- `render_report()` emits `## Winner/Loser Characteristic Analysis (Pre-registered)` section between ATR-multiple and Gate Attribution sections
- `json_out['wl_analysis']` added with exact UI-SPEC JSON shape

### tests/test_report.py
- `_wl_signal()` helper for W/L test fixtures
- 8 new test functions: `test_wl_features_is_constant`, `test_wl_analysis_abort`, `test_wl_analysis_basic`, `test_wl_analysis_six_metrics`, `test_wl_analysis_per_strategy`, `test_wl_analysis_suppressed`, `test_wl_analysis_has_industry_momentum`, `test_render_report_has_wl_analysis`

## Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| 1 | 28e13e5 | feat | Signal 4 new fields + backtest metric capture |
| 2 | 2d551c5 | feat | WL_FEATURES constants + functions + render_report() |
| 3 | ff35f52 | test | 8 W/L tests covering WLA-01 through WLA-06 |

## Verification Results

- `pytest tests/test_report.py -q`: 42 passed (34 pre-existing + 8 new)
- `pytest -q` full suite: 239 passed offline
- Smoke check `python -c "...WL_FEATURES...wl_characteristic_analysis([], [])..."`: OK

## Requirements Coverage

| Req | Description | Status |
|-----|-------------|--------|
| WLA-01 | render_report() emits wl_analysis in json_out for >= 200 trades | Covered by test_render_report_has_wl_analysis |
| WLA-02 | Metric rows are exactly WL_FEATURES in order | Covered by test_wl_analysis_six_metrics |
| WLA-03 | Per-strategy grouping (never combined) | Covered by test_wl_analysis_per_strategy |
| WLA-04 | Industry momentum always present | Covered by test_wl_analysis_has_industry_momentum |
| WLA-05 | Abort < 200 total; suppress < 50 per bucket | Covered by test_wl_analysis_abort + test_wl_analysis_suppressed |
| WLA-06 | WL_FEATURES is pre-registered constant in source | Covered by test_wl_features_is_constant |

## Deviations from Plan

None — plan executed exactly as written.

Task 3 has `tdd="true"` but implementation (Task 2) precedes tests (Task 3) by plan design. Tests were written after the implementation was committed and passed immediately. This is the plan's explicit ordering; no RED/GREEN cycle was required since the plan frontmatter is `type: execute`, not `type: tdd`.

## Known Stubs

None. All 6 metric rows are computed from real Signal/Trade fields. Where data is unavailable (e.g., pullback_depth_pct for breakout signals) the median resolves to None, rendered as `—` — this is correct behavior, not a stub.

## Threat Flags

None. As assessed in the plan's threat model: wl_analysis is written only by the internal backtest command from trusted Signal/Trade objects; no new attack surface.

## Self-Check

| Item | Status |
|------|--------|
| SUMMARY.md created | FOUND |
| Commit 28e13e5 (Task 1) | FOUND |
| Commit 2d551c5 (Task 2) | FOUND |
| Commit ff35f52 (Task 3) | FOUND |

## Self-Check: PASSED
