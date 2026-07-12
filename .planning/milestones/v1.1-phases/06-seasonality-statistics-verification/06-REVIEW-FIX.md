---
phase: 06-seasonality-statistics-verification
fixed_at: 2026-07-10T12:43:37Z
review_path: .planning/phases/06-seasonality-statistics-verification/06-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-07-10T12:43:37Z
**Source review:** .planning/phases/06-seasonality-statistics-verification/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (1 Critical/BLOCKER + 3 Warnings; scope = `critical_warning`, IN-01/IN-02 out of scope)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: `bootstrap_week_ci` silently returns NaN CI / false "not significant" for weeks missing from any single year

**Files modified:** `scanner/seasonality.py`, `tests/test_seasonality.py`
**Commit:** f6b47ab
**Applied fix:** Adapted the review's minimal-fix guidance to the real trigger mechanism, which I reproduced directly before fixing: `np.percentile` (not `np.nanpercentile`) returns `NaN` for the ENTIRE column the instant even a single bootstrap draw is `NaN` for a week — not only when literally every draw misses it. Replaced `np.percentile` with `np.nanpercentile` so a partial-miss draw no longer poisons the whole CI (the common realistic case: a week present in the panel but absent from one distinct year now gets a real, non-NaN CI computed from the draws that did capture it). Added an `insufficient_years` boolean column, set `True` only when literally every draw missed the week (`np.all(np.isnan(delta), axis=0)`) — the genuinely uncomputable edge case — and forced `significant = False` whenever that flag is set, so the result is never silently indistinguishable from a legitimately-computed "not significant." Also propagated `insufficient_years` through to `compute_seasonality_stats`'s merged output so Phase 7 can see it.

Note: my first attempt computed `insufficient_years` by comparing each week's per-year data coverage against the panel's total distinct-year count. That produced a false positive on the existing `test_synthetic_injected_week28_effect_flagged_significant` test — natural ISO-year boundary fragments (e.g. a handful of trailing December days rolling into an otherwise-empty 21st ISO year) legitimately lack data for most interior weeks without being a real support problem. I corrected the flag to be data-driven from the actual bootstrap draws (`all_nan`) instead, re-verified against the full suite, and it no longer produces false positives.

Added two regression tests: `test_bootstrap_ci_week_missing_from_one_year_no_longer_silently_nan` (the realistic partial-miss reproduction from the review — asserts the CI is now a real number, not NaN) and `test_bootstrap_ci_week_never_drawn_flagged_insufficient_years` (a deterministic edge case, using a monkeypatched fixed-draw RNG to force every single draw to miss the sparse week — asserts `insufficient_years=True`, `significant` forced `False`, and CI bounds remain `NaN` but are now explicitly flagged rather than silent).

### WR-01: `--seed` has no explicit input validation despite being named alongside `--bootstrap-iters` in the phase's ASVS V5 control

**Files modified:** `scanner/seasonality.py`, `tests/test_seasonality.py`
**Commit:** efbfcbf
**Applied fix:** Added `if seed < 0: raise ValueError(f"seed must be a non-negative integer, got {seed}")` in `bootstrap_week_ci`, placed alongside the existing `iters` validation before any array allocation, matching the module's descriptive-`ValueError` convention. Added `test_bootstrap_ci_seed_negative_raises` and `test_bootstrap_ci_seed_zero_does_not_raise`.

### WR-02: No upper bound on `--bootstrap-iters` — arbitrarily large values allocate unbounded memory instead of failing with a clear error

**Files modified:** `scanner/seasonality.py`, `tests/test_seasonality.py`
**Commit:** a6cee4d
**Applied fix:** Added a module-level `_MAX_BOOTSTRAP_ITERS = 100_000` constant and extended the existing guard to `if iters <= 0 or iters > _MAX_BOOTSTRAP_ITERS: raise ValueError(...)`, exactly as suggested. Added `test_bootstrap_ci_iters_above_ceiling_raises` and `test_bootstrap_ci_iters_at_ceiling_does_not_raise`.

### WR-03: `compute_log_returns` drops leading NaN but not `-inf`/`inf` from non-positive Close prices

**Files modified:** `scanner/seasonality.py`, `tests/test_seasonality.py`
**Commit:** 660402f
**Applied fix:** Added `log_ret_bps = log_ret_bps.replace([np.inf, -np.inf], np.nan)` immediately after computing `log_ret_bps`, before the existing `dropna(subset=["log_ret_bps"])` — so any zero/negative `Close` value (which produces `-inf` on its own row and `inf`/`NaN` on the following row) is dropped like any other missing observation instead of poisoning every downstream sum/mean. Added `test_compute_log_returns_zero_close_drops_inf_not_poisons_panel` (verifies the `-inf`/`+inf` pair around a zero-Close row is dropped, leaving only the unaffected row) and `test_compute_log_returns_negative_close_drops_inf_not_poisons_panel` (negative Close already produced `NaN` via `np.log`, not `inf`, so this is defensive coverage rather than a discriminating regression test, but confirms no lingering inf/NaN leaks through).

## Skipped Issues

None — all 4 in-scope findings were fixed.

## Verification

Full test suite run after all four fixes: `pytest -q` → **295 passed** (2 harmless `RuntimeWarning`s expected from the WR-03 zero/negative-Close test fixtures calling `np.log` on non-positive values — not failures).

## Out of Scope

IN-01 (`std_bps` NaN for single-observation weeks) and IN-02 (`SectorDataset.universe` normalization inconsistency) were left untouched per `fix_scope: critical_warning` — Info-level findings are excluded from this pass.

---

_Fixed: 2026-07-10T12:43:37Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
