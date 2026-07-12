---
phase: 06-seasonality-statistics-verification
plan: 02
subsystem: testing
tags: [numpy, bootstrap, statistics, pandas, resampling]

# Dependency graph
requires:
  - phase: 06-seasonality-statistics-verification
    provides: "06-01 — compute_log_returns/week_observed_stats ISO-tagged panel + observed per-week stats"
provides:
  - check_thin_data — D-05 abort guard for dataset-wide distinct-year count below 5
  - bootstrap_week_ci — reproducible year-block percentile bootstrap 95% CI + significance flag per week
affects: [06-03-synthetic-verification, phase-07-presentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Year-block bootstrap via precomputed (n_years, 52) sum/count matrices + numpy fancy-indexing (no per-iteration pandas groupby loop)"
    - "numpy.random.default_rng(seed) Generator API for all new reproducible randomness — never the legacy global np.random.seed"
    - "Dataset-wide abort tier (ValueError, no skip-list) vs. per-ticker skip-not-fail tier stays a hard distinction (D-05)"

key-files:
  created: []
  modified:
    - scanner/seasonality.py
    - tests/test_seasonality.py

key-decisions:
  - "check_thin_data mirrors resolve_sector's descriptive ValueError-abort pattern exactly — states found vs. required counts, no log-and-continue"
  - "bootstrap_week_ci validates iters<=0 BEFORE allocating the (iters, n_years) draw array (T-6-01 mitigation)"
  - "Baseline is recomputed per bootstrap iteration from the same resampled draw, never held fixed at the observed value (RESEARCH.md Pitfall 4)"
  - "Significance test uses a zero-variance-across-years panel (identical value every year) so the bootstrap CI collapses to an exact deterministic point — avoids any flakiness in asserting the CI-excludes-zero boundary"

patterns-established:
  - "Vectorized year-block bootstrap: build sum/count matrices once, then rng.integers(0, n_years, size=(iters, n_years)) + fancy indexing reproduces every iteration's resampled week mean AND resampled baseline in one shot"

requirements-completed: [SEAS-08, SEAS-09]

coverage:
  - id: D1
    description: "check_thin_data aborts (ValueError) before any bootstrap work when the panel spans fewer than 5 distinct ISO years, dataset-wide (not per-ticker); returns None at or above the floor, and honors a custom min_years override"
    requirement: "SEAS-08"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_check_thin_data_four_years_raises"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_check_thin_data_five_years_returns_none"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_check_thin_data_twenty_years_returns_none"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_check_thin_data_custom_min_years_honored"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_check_thin_data_dataset_wide_not_per_ticker"
        status: pass
    human_judgment: false
  - id: D2
    description: "bootstrap_week_ci produces a reproducible 95% CI per week via a vectorized year-block bootstrap (same seed -> identical bounds/flags; different seed -> at least one differing bound), with the baseline resampled per iteration rather than held fixed"
    requirement: "SEAS-08"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_bootstrap_ci_columns_exact"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_bootstrap_ci_reproducible_same_seed"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_bootstrap_ci_different_seed_differs"
        status: pass
    human_judgment: false
  - id: D3
    description: "A week is flagged significant iff its 95% CI excludes zero (ci_low>0 or ci_high<0); a week whose CI straddles zero is not significant"
    requirement: "SEAS-09"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_bootstrap_ci_significance_rule"
        status: pass
    human_judgment: false
  - id: D4
    description: "bootstrap_week_ci raises ValueError for iters<=0 before allocating the resampling array (T-6-01, ASVS V5)"
    requirement: "SEAS-08"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_bootstrap_ci_iters_zero_raises"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_bootstrap_ci_iters_negative_raises"
        status: pass
    human_judgment: false

duration: ~12min
completed: 2026-07-10
status: complete
---

# Phase 6 Plan 02: Year-Block Bootstrap CI & Thin-Data Guard Summary

**Vectorized numpy year-block percentile bootstrap producing a reproducible 95% CI per week (baseline resampled per iteration) plus the D-05 thin-data abort guard, both proven by deterministic unit tests**

## Performance

- **Duration:** ~12 min
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- `_MIN_BOOTSTRAP_YEARS = 5` module constant added alongside `_MIN_HISTORY_DAYS`, with a comment clarifying it's a separate, higher bar gating the bootstrap rather than ticker admission
- `check_thin_data(panel, min_years=_MIN_BOOTSTRAP_YEARS)` raises a descriptive `ValueError` when the panel's distinct `iso_year` count (dataset-wide, not per ticker) falls below the floor; returns `None` otherwise — mirrors `resolve_sector`'s abort pattern exactly, no log-and-continue
- `bootstrap_week_ci(panel, iters, seed)` implements the verified vectorized sum/count-matrix year-block bootstrap: builds a `(n_years, 52)` sum/count matrix once, draws `(iters, n_years)` year-indices via `numpy.random.default_rng(seed).integers(...)`, sums via fancy indexing, and recomputes the baseline fresh from the SAME resampled draw each iteration (never held fixed at the observed value)
- `significant = (ci_low_bps > 0) | (ci_high_bps < 0)` — a pure CI-excludes-zero rule with no tunable test statistic
- `iters <= 0` raises `ValueError` before any array allocation (mitigates T-6-01 / ASVS V5)
- Verified empirically (interactive, before committing): 1000 iterations on a 20-year/15-ticker synthetic panel ran in ~51ms, matching RESEARCH.md's ~50ms benchmark; same-seed calls are bit-identical, different seeds diverge, and an injected -30bps week-28 effect is correctly flagged significant with CI (-34.9, -21.7) bps

## Task Commits

Each task was committed atomically:

1. **Task 1: check_thin_data — D-05 distinct-year guard** - `5e716b3` (feat)
2. **Task 2: bootstrap_week_ci — vectorized year-block percentile bootstrap + significance** - `160dd12` (feat)
3. **Task 3: Unit tests for check_thin_data + bootstrap_week_ci + significance rule** - `7b77c11` (test)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `scanner/seasonality.py` - added `_MIN_BOOTSTRAP_YEARS`, `check_thin_data`, `bootstrap_week_ci`
- `tests/test_seasonality.py` - added `check_thin_data`/`bootstrap_week_ci` test banners with 11 new test cases (5 thin_data, 6 bootstrap_ci/significance)

## Decisions Made
- `check_thin_data`'s error message states both the found and required distinct-year counts (mirroring `resolve_sector`'s "state actual vs. required" convention), and it is verified in tests to NOT append to a skip list or call `_log.warning` — it is strictly the "abort the whole run" tier, distinct from Phase 5's per-ticker skip-not-fail tier
- The significance-rule test builds a panel where each week's value is identical across every year (zero across-year variance), causing the year-block bootstrap CI to collapse to an exact deterministic point per week. This makes the CI-excludes-zero boundary test fully deterministic and non-flaky, rather than relying on a noisy CI landing reliably on one side of zero
- The reproducibility/seed-sensitivity tests use a separate helper (`_build_bootstrap_panel`) with genuine `default_rng`-seeded noise across 6 years/5 tickers, since those tests need real resampling variance (not the zero-variance panel used for the significance test)
- Test names for bootstrap CI tests use the substring `bootstrap_ci` (not `bootstrap_week_ci`) to match the plan's acceptance-criteria filter `-k "bootstrap_ci or significant"`

## Deviations from Plan

None - plan executed exactly as written. As in Plan 01, Tasks 1 and 2 are marked `tdd="true"` in the plan but their `<action>` sections describe implementation only (no test-writing instructions), while Task 3 is the plan's dedicated test-authoring task covering both functions per its own `<action>`/`<behavior>` spec. Implementation correctness for Tasks 1-2 was verified via direct interactive execution (matching RESEARCH.md's empirically-verified parameters and boundary cases) before each commit, then Task 3 added the permanent pytest coverage exactly as the plan specified.

## TDD Gate Compliance

Task 1 and Task 2 are marked `tdd="true"` in PLAN.md, but per the plan's own `<action>` text they are implementation-only tasks (test authorship is explicitly deferred to Task 3, which is not marked `tdd="true"`). No `test(...)` commit precedes the `feat(...)` commits for these tasks — this is a literal reading of the plan's own task boundaries (identical precedent set in 06-01-SUMMARY.md), not a RED/GREEN/REFACTOR gate violation, since the plan itself does not ask for a RED-phase test inside Tasks 1-2. Correctness was still verified via direct interactive execution against RESEARCH.md's empirically-verified expected values before each commit.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `check_thin_data` and `bootstrap_week_ci` are ready inputs for Plan 03's `compute_seasonality_stats` orchestrator and the synthetic verification tests (SEAS-14/15)
- Full test suite: 280 passed (up from 269 after Plan 01)

---
*Phase: 06-seasonality-statistics-verification*
*Completed: 2026-07-10*

## Self-Check: PASSED
