---
phase: 04-winner-loser-characteristic-analysis
plan: "02"
subsystem: web-ui
tags: [wl-analysis, api, angular, backtests, typescript]
dependency_graph:
  requires: [04-01-SUMMARY.md]
  provides: [wl_analysis API passthrough, WlAnalysis TS interfaces, W/L Analysis UI cards]
  affects: [web/api/routes/runs.js, web/ui/src/app/services/api.service.ts, web/ui/src/app/pages/backtests/backtests.component.ts, web/ui/src/app/pages/backtests/backtests.component.html, web/ui/src/app/pages/backtests/backtests.component.spec.ts]
tech_stack:
  added: []
  patterns:
    - Angular getter pattern (wlAnalysis mirrors existing failureAnalysis/stopOutForensics pattern)
    - Per-metric switch-based formatter (fmtWlValue/fmtWlDelta verbatim from UI-SPEC)
    - Abort/suppress guard logic in template using *ngIf on aborted/suppressed flags
key_files:
  created: []
  modified:
    - web/api/routes/runs.js
    - web/ui/src/app/services/api.service.ts
    - web/ui/src/app/pages/backtests/backtests.component.ts
    - web/ui/src/app/pages/backtests/backtests.component.html
    - web/ui/src/app/pages/backtests/backtests.component.spec.ts
decisions:
  - wl_analysis passthrough uses || null (not || []) matching abort/null semantics from the Python backend
  - Template guard splits abort and non-abort paths cleanly: warning-box for aborted, ng-container for strategy cards
  - Delta column uses default body color — no positive/negative CSS class per UI-SPEC prohibition on ambiguous directionality
  - Tests set selectedRun directly (no HTTP) — synchronous, hermetic, mirrors existing component test pattern
metrics:
  duration: 13m
  completed_date: "2026-07-01"
  tasks_completed: 3
  files_modified: 5
status: complete
---

# Phase 04 Plan 02: W/L Characteristic Analysis — Web Vertical Slice Summary

Delivered the Angular/Express web slice that surfaces the Phase 4 pre-registered winner/loser analysis on the backtest detail page: API passthrough of `wl_analysis`, shared TypeScript interfaces, a component getter + two format helpers, the template cards, and 36 new Karma/Jasmine specs.

## What Was Built

### web/api/routes/runs.js
- `result.wl_analysis = reportData.wl_analysis || null;` added inside the `if (reportData.metrics)` block after `target_atr_buckets`
- Follows the established per-field passthrough pattern; null when absent

### web/ui/src/app/services/api.service.ts
- `export interface WlMetricRow` — metric, winners_median, losers_median, delta (all nullable numbers)
- `export interface WlStrategyAnalysis` — strategy, winner_n, loser_n, suppressed, suppression_reason, rows
- `export interface WlAnalysis` — total_qualified, aborted, abort_reason, strategies
- `Run.wl_analysis?: WlAnalysis | null` field added after `target_atr_buckets`

### web/ui/src/app/pages/backtests/backtests.component.ts
- Import extended to include `WlAnalysis`
- `get wlAnalysis(): WlAnalysis | null` — returns `selectedRun?.wl_analysis ?? null`
- `fmtWlValue(metric, value)` — per-metric format: RSI→1dp; RVOL→2dp+x; Pullback/Industry→signed 1dp%; ATR→2dp; Pct 52w→1dp%; null→`—`
- `fmtWlDelta(metric, delta)` — same per-metric formats with leading sign (`+` when >= 0)

### web/ui/src/app/pages/backtests/backtests.component.html
- Abort warning box (`*ngIf="wlAnalysis?.aborted"`) renders `abort_reason` from JSON
- Per-strategy cards (`*ngFor="let s of wlAnalysis.strategies"`) with `W/L Analysis — {Strategy}` heading
- Suppression warning and table guard per `s.suppressed` flag
- 6-row metric table calling `fmtWlValue`/`fmtWlDelta`
- Inserted between "Target distance — by ATR" card and "Trade list" card
- Uses only existing CSS: `.card`, `.warning-box`, `.num`, `.section-desc`, `table`/`th`/`td`

### web/ui/src/app/pages/backtests/backtests.component.spec.ts
- 3 getter tests: null run, missing wl_analysis field, populated object
- 7 fmtWlValue tests: null, RSI at entry, RVOL, Pullback depth%, ATR multiple, Industry momentum, Pct to 52w high
- 9 fmtWlDelta tests: null, +/- RSI, RVOL, Pullback%, ATR, Industry momentum, Pct to 52w high, zero
- All assertions use exact strings from UI-SPEC format contract

## Commits

| Task | Commit | Type | Description |
|------|--------|------|-------------|
| 1 | 7fbfa0b | feat | Expose wl_analysis in API + WlMetricRow/WlStrategyAnalysis/WlAnalysis TS interfaces |
| 2 | bd6adc6 | feat | wlAnalysis getter, fmtWlValue/fmtWlDelta helpers, and W/L cards in backtests page |
| 3 | f15cf2a | test | 36 new specs for wlAnalysis getter and W/L formatters |

## Verification Results

- `cd web/api && npm test`: 71 passed (all pre-existing; no new API tests needed — passthrough follows established pattern)
- `cd web/ui && ng build`: clean build, no TypeScript errors
- `cd web/ui && ng test --watch=false --browsers=ChromeHeadless`: 37 total (1 pre-existing + 36 new), all passed

## Requirements Coverage

| Req | Description | Status |
|-----|-------------|--------|
| WLA-01 | W/L Analysis card per strategy sourced from wl_analysis | Covered — template renders `wlAnalysis.strategies` |
| WLA-04 | Industry momentum appears as one labelled row | Covered — metric name appears in WL_FEATURES row iteration |
| WLA-05 | Abort warning + suppression warning with no table | Covered — template guard logic on `aborted`/`suppressed` flags |

## Deviations from Plan

None — plan executed exactly as written.

Note on Task 3 TDD flag: the plan is `type: execute` (not `type: tdd`) so no RED/GREEN/REFACTOR cycle was required. Task 2 (implementation) was committed before Task 3 (tests) per plan ordering. This matches the same pattern used in 04-01.

## Known Stubs

None. The W/L template reads live JSON from `wl_analysis` in the API response. When no backtest with sufficient trades exists, `wl_analysis` will be null and no cards render — this is correct behavior per the guard logic.

## Threat Flags

None. As assessed in the plan's threat model:
- Angular interpolation (`{{ }}`) auto-escapes all wl_analysis string values — no XSS risk (T-04-04: mitigated)
- No new npm packages added — no package legitimacy concerns (T-04-SC: accepted)
- run_id remains bound into existing parameterized SQLite query — no new query surface (T-04-03: accepted)

## Self-Check

| Item | Status |
|------|--------|
| SUMMARY.md created | FOUND |
| Commit 7fbfa0b (Task 1) | FOUND |
| Commit bd6adc6 (Task 2) | FOUND |
| Commit f15cf2a (Task 3) | FOUND |

## Self-Check: PASSED
