---
phase: 06-seasonality-statistics-verification
plan: 01
subsystem: testing
tags: [pandas, numpy, isocalendar, statistics, seasonality]

# Dependency graph
requires:
  - phase: 05-sector-resolution-data-input
    provides: SectorDataset.frames — validated {ticker: DataFrame} OHLCV sets
provides:
  - compute_log_returns — pools admitted tickers' daily log returns into one ISO-tagged panel
  - week_observed_stats — per-week mean/median/std/n_obs/n_years plus delta vs. pooled baseline
  - SeasonalityResult dataclass shell for the Plan 03 orchestrator
affects: [06-02-bootstrap-ci, 06-03-synthetic-verification, phase-07-presentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ISO year/week always sourced from the same df.index.isocalendar() call — never df.index.year"
    - "Dataclass-as-result-container (SeasonalityResult mirrors SectorDataset)"
    - "Pooled full-sample baseline is a flat mean over every ticker-day row (D-01), not an average of per-week means"

key-files:
  created: []
  modified:
    - scanner/seasonality.py
    - tests/test_seasonality.py

key-decisions:
  - "Baseline for delta_vs_baseline_bps is panel['log_ret_bps'].mean() — flat over every ticker-day row, matching D-01 pooling"
  - "Multi-day internal gaps within a ticker's cached history are not specially handled (accepted simplification per RESEARCH.md Pitfall 5)"
  - "week_observed_stats returns only weeks actually present in the panel — no padding to 52 rows (Phase 7's concern)"

patterns-established:
  - "Statistics-stage functions in scanner/seasonality.py are pure transforms: no I/O, no wall-clock date, input/output are plain DataFrames"

requirements-completed: [SEAS-06, SEAS-07]

coverage:
  - id: D1
    description: "compute_log_returns pools every admitted ticker's daily log return into one ISO-tagged panel, week 53 merged into 52, leading NaN dropped"
    requirement: "SEAS-06"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_compute_log_returns_columns_and_values"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_compute_log_returns_pooling_two_tickers_sums_row_counts"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_compute_log_returns_isocalendar_week53_merged_into_52"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_compute_log_returns_isocalendar_year_boundary_maps_to_next_iso_year"
        status: pass
    human_judgment: false
  - id: D2
    description: "week_observed_stats reports pooled mean/median/std/n_obs/n_years per week and each week's delta vs. the pooled full-sample baseline"
    requirement: "SEAS-07"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_week_observed_stats_columns_exact"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_week_observed_stats_week10_mean_n_obs_n_years_and_baseline_delta"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_week_observed_stats_baseline_delta_matches_plan_hand_computed_example"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_week_observed_stats_sorted_ascending_by_week"
        status: pass
    human_judgment: false

duration: ~10min
completed: 2026-07-10
status: complete
---

# Phase 6 Plan 01: Log-Return Panel & Observed Week Stats Summary

**Pooled ISO-week log-return panel builder plus per-week mean/median/std/n_obs/n_years and baseline delta, using `.isocalendar()` for correct year-boundary and week-53 handling**

## Performance

- **Duration:** ~10 min
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- `compute_log_returns(frames)` pools every admitted ticker's daily log return (`np.log(Close).diff() * 10_000`) into one long panel tagged with ISO year/week, remapping week 53 to 52 and dropping the leading NaN row per ticker
- `week_observed_stats(panel)` computes pooled mean/median/std/n_obs/n_years per week plus `delta_vs_baseline_bps` against the flat full-sample pooled mean (D-01)
- `SeasonalityResult` dataclass shell added for Plan 03's orchestrator
- Verified empirically that `2019-12-30` maps to ISO year 2020/week 1 and `2020-12-28` maps to week 52 (no week 53 ever appears in output)

## Task Commits

Each task was committed atomically:

1. **Task 1: compute_log_returns panel builder + SeasonalityResult dataclass** - `46a009a` (feat)
2. **Task 2: week_observed_stats — per-week stats + baseline delta** - `d1a4181` (feat)
3. **Task 3: Unit tests for compute_log_returns + week_observed_stats + baseline delta** - `477b3e1` (test)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `scanner/seasonality.py` - added `import numpy as np`, Phase 6 docstring paragraph, `SeasonalityResult` dataclass, `compute_log_returns`, `week_observed_stats`
- `tests/test_seasonality.py` - added `compute_log_returns`/`week_observed_stats` test banners with 9 new test cases

## Decisions Made
- Baseline for `delta_vs_baseline_bps` computed once as `panel["log_ret_bps"].mean()` (flat pooled mean over every ticker-day row), matching D-01 and the plan's explicit warning against summing per-week means
- `week_observed_stats` returns only weeks actually present in the panel — no padding to a fixed 52 rows (left to Phase 7)
- Multi-day internal gaps within a ticker's cached history are not specially detected/handled — documented as an accepted simplification consistent with RESEARCH.md Pitfall 5 ("no silent smoothing")

## Deviations from Plan

None - plan executed exactly as written. Tasks 1 and 2 are marked `tdd="true"` in the plan but their `<action>` sections describe implementation only (no test-writing instructions), while Task 3 is the plan's dedicated test-authoring task covering both functions per its own `<action>`/`<behavior>` spec. Implementation correctness for Tasks 1-2 was verified via direct interactive execution (matching the plan's own empirically-verified boundary cases from RESEARCH.md) before each commit, then Task 3 added the permanent pytest coverage exactly as the plan specified. This is a literal-task-boundary execution of the plan's own structure, not a deviation from it.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `compute_log_returns` and `week_observed_stats` are ready inputs for Plan 02's year-block bootstrap CI (`bootstrap_week_ci`) and thin-data guard (`check_thin_data`)
- `SeasonalityResult`'s shape is declared; Plan 03's orchestrator (`compute_seasonality_stats`) will populate it from these two functions plus Plan 02's bootstrap output
- Full test suite: 269 passed (up from 260)

---
*Phase: 06-seasonality-statistics-verification*
*Completed: 2026-07-10*

## Self-Check: PASSED
