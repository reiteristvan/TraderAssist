---
phase: 06-seasonality-statistics-verification
plan: 03
subsystem: testing
tags: [pandas, numpy, bootstrap, statistics, seasonality, cli]

# Dependency graph
requires:
  - phase: 06-seasonality-statistics-verification
    provides: "06-01 — compute_log_returns/week_observed_stats; 06-02 — check_thin_data/bootstrap_week_ci"
provides:
  - compute_seasonality_stats — single entry point composing the four Phase 6 stages into one SeasonalityResult
  - seasonality_by_week.py --bootstrap-iters/--seed live wiring (CLI half of SEAS-08)
  - synthetic verification proving SEAS-14 (injected-effect detection) and SEAS-15 (bounded false-positive rate)
affects: [phase-07-presentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "compute_seasonality_stats mirrors load_sector_dataset's compose-small-functions + validate-first orchestrator shape"
    - "Synthetic SectorDataset fixtures built directly from log-return arrays exponentiated into a Close series, so compute_log_returns recovers the same returns end-to-end"

key-files:
  created: []
  modified:
    - scanner/seasonality.py
    - seasonality_by_week.py
    - tests/test_seasonality.py
    - tests/test_seasonality_cli.py

key-decisions:
  - "_DEFAULT_BOOTSTRAP_ITERS=1000/_DEFAULT_SEED=42 resolved inside compute_seasonality_stats (None -> default), never in the CLI — keeps the CLI thin per the established years-arg convention"
  - "weeks DataFrame column order is the 9 SEAS-10 names first, then std_bps appended last (carried for Phase 7, not in SEAS-10's own table)"
  - "_synthetic_panel builds a business-day range from calendar year N to N+n_years-1 (not periods=n_years*261) — this exact construction reproduced RESEARCH.md's stated week-28 CI (-39.8,-24.1) bps almost exactly"

patterns-established:
  - "CLI wiring calls the engine's compute_seasonality_stats inside the existing ValueError->exit-2 try block, no new error-handling shape introduced"

requirements-completed: [SEAS-14, SEAS-15]

coverage:
  - id: D1
    description: "compute_seasonality_stats composes compute_log_returns -> check_thin_data -> week_observed_stats -> bootstrap_week_ci into one SeasonalityResult with the full 9-column SEAS-10 set plus std_bps, applying D-03/D-04 defaults and the D-05 guard"
    requirement: "SEAS-08"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_compute_seasonality_stats_columns_and_defaults"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_compute_seasonality_stats_explicit_args_override_defaults"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_compute_seasonality_stats_thin_dataset_raises_before_bootstrap"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_compute_seasonality_stats_baseline_and_n_years_match_panel"
        status: pass
    human_judgment: false
  - id: D2
    description: "--bootstrap-iters/--seed are live in seasonality_by_week.py, passed through to compute_seasonality_stats; the thin-data/iters ValueError surfaces as exit code 2; a plain per-run summary is printed"
    requirement: "SEAS-08"
    verification:
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_happy_path_prints_summary"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_thin_data_value_error_exits_2"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_default_universe_is_sp500"
        status: pass
    human_judgment: false
  - id: D3
    description: "Synthetic 20yr/15-ticker/150bps panel with an injected -30bps week-28 effect flags week 28 significant with CI entirely below zero"
    requirement: "SEAS-14"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_synthetic_injected_week28_effect_flagged_significant"
        status: pass
    human_judgment: false
  - id: D4
    description: "Same synthetic panel construction with pure noise (no injection) flags between 0 and 3 of 52 weeks significant"
    requirement: "SEAS-15"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_synthetic_noise_flags_0_to_3_of_52"
        status: pass
    human_judgment: false

duration: ~15min
completed: 2026-07-10
status: complete
---

# Phase 6 Plan 03: compute_seasonality_stats Orchestrator, Live CLI Wiring & Synthetic Verification Summary

**compute_seasonality_stats composes the full Phase 6 pipeline into one SeasonalityResult, `--bootstrap-iters`/`--seed` are now live in the CLI, and a 20-year/15-ticker synthetic panel proves both injected-effect detection (SEAS-14) and a bounded false-positive rate (SEAS-15)**

## Performance

- **Duration:** ~15 min
- **Tasks:** 3
- **Files modified:** 4 (one beyond the plan's declared 3 — see Deviations)

## Accomplishments
- `_DEFAULT_BOOTSTRAP_ITERS = 1000` and `_DEFAULT_SEED = 42` module constants added to `scanner/seasonality.py` (D-03/D-04)
- `compute_seasonality_stats(dataset, bootstrap_iters=None, seed=None) -> SeasonalityResult` composes `compute_log_returns -> check_thin_data -> week_observed_stats -> bootstrap_week_ci`, merges the observed and CI frames on `week` into the 9 SEAS-10 columns plus `std_bps`, and populates `baseline_mean_bps`/`n_years` from the pooled panel
- `seasonality_by_week.py`'s `--bootstrap-iters`/`--seed` help text now describes live behavior; `main()` calls `compute_seasonality_stats` inside the existing ValueError->exit-2 try block and prints a plain summary line (baseline, n_years, bootstrap_iters, seed, significant-week count)
- `_synthetic_panel` test helper builds a `SectorDataset` of N synthetic tickers spanning N calendar years of business days from one shared `default_rng(seed)`, with an optional constant per-week bps injection; verified this construction reproduces RESEARCH.md's stated week-28 injected CI of approximately (-39.8, -24.1) bps almost exactly
- Two synthetic verification tests pass deterministically at the RESEARCH.md-locked seeds: injected -30bps week-28 effect flags week 28 significant with CI entirely below zero (SEAS-14); pure-noise run flags 2 of 52 weeks, within the 0-3 band (SEAS-15)

## Task Commits

Each task was committed atomically:

1. **Task 1: compute_seasonality_stats orchestrator** - `2e8f767` (feat)
2. **Task 2: Wire --bootstrap-iters/--seed into seasonality_by_week.py** - `ab01804` (feat)
3. **Task 3: Synthetic verification tests (SEAS-14, SEAS-15)** - `27b0aca` (test)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `scanner/seasonality.py` - added `_DEFAULT_BOOTSTRAP_ITERS`, `_DEFAULT_SEED`, `compute_seasonality_stats`
- `seasonality_by_week.py` - live `--bootstrap-iters`/`--seed` help text; `main()` calls `compute_seasonality_stats`, prints per-run summary
- `tests/test_seasonality.py` - added `_synthetic_panel` helper, 4 general `compute_seasonality_stats` unit tests, and the SEAS-14/SEAS-15 synthetic verification tests
- `tests/test_seasonality_cli.py` - updated existing CLI tests to mock `compute_seasonality_stats` (see Deviations), added a thin-data-guard exit-2 regression test

## Decisions Made
- `compute_seasonality_stats` resolves `bootstrap_iters=None`/`seed=None` to the module defaults internally (not in the CLI), matching the existing `years` pass-through convention in `load_sector_dataset`
- The merged `weeks` DataFrame orders columns as the 9 SEAS-10 names first, then `std_bps` last (SEAS-06 needs it carried even though SEAS-10's own table omits it — left for Phase 7)
- `_synthetic_panel` uses `pd.bdate_range(start=f"{base_year}-01-01", end=f"{base_year+n_years-1}-12-31", freq="B")` rather than an approximate `periods=n_years*261` — this exact construction was verified interactively to reproduce RESEARCH.md's stated week-28 injected CI almost exactly, confirming it matches the research session's own prototype methodology

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated tests/test_seasonality_cli.py to mock compute_seasonality_stats**
- **Found during:** Task 2 (wiring `--bootstrap-iters`/`--seed` into `seasonality_by_week.py`)
- **Issue:** The plan's `files_modified` list only named `seasonality_by_week.py`, but making `main()` unconditionally call `compute_seasonality_stats` broke the two existing happy-path tests in `tests/test_seasonality_cli.py` (`test_main_happy_path_prints_summary`, `test_main_default_universe_is_sp500`) — they constructed a fake `SectorDataset` with a 2-row tiny frame and only mocked `load_sector_dataset`, so the real `compute_seasonality_stats` call hit the thin-data guard and returned exit code 2 instead of 0.
- **Fix:** Added a `_fake_result()` helper returning a `SeasonalityResult`, monkeypatched `scanner.seasonality.compute_seasonality_stats` in both affected tests, and extended assertions to cover the new summary print (bootstrap iters/seed/significant-week count). Also added a new `test_main_thin_data_value_error_exits_2` regression test to explicitly cover the plan's stated "ValueError from the engine surfaces as exit 2" behavior, which the plan's `<verify>` step implicitly required but no existing test covered.
- **Files modified:** tests/test_seasonality_cli.py
- **Verification:** `pytest -q tests/test_seasonality_cli.py` (4 passed) and full suite `pytest -q` (287 passed)
- **Committed in:** ab01804 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to keep the existing test suite green after making the CLI call the new engine function unconditionally, exactly as the plan's `<behavior>`/`<verify>` sections required. No scope creep — only the test file needed updating, no production behavior changed beyond what the plan specified.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 is complete: `compute_seasonality_stats` is the single entry point Phase 7 will consume for its table/summary rendering; `SeasonalityResult.weeks` carries all 9 SEAS-10 rendering columns plus `std_bps`
- `--bootstrap-iters`/`--seed` are fully live end-to-end (CLI arg -> engine default resolution -> reproducible bootstrap)
- Full test suite: 287 passed (up from 280 after Plan 02)

---
*Phase: 06-seasonality-statistics-verification*
*Completed: 2026-07-10*

## Self-Check: PASSED
