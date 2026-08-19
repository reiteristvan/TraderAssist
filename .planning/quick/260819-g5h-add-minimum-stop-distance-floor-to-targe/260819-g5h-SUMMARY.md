---
task: quick-260819-g5h
title: Add minimum stop-distance floor to targets.py stop engine
status: complete
subsystem: scanner/targets.py
tags: [trading-logic, stop-engine, risk-management]
dependency-graph:
  requires: []
  provides: [apply_min_stop_floor, MIN_STOP_ATR_MULT]
  affects: [scanner/targets.py::attach_risk]
tech-stack:
  added: []
  patterns: [total-function-guard, floor-not-round-quantization]
key-files:
  created: []
  modified:
    - scanner/targets.py
    - tests/test_targets.py
decisions:
  - "0.5x ATR minimum stop-distance floor (D-01), widen-not-drop (D-02), applies to both strategies (D-03), no schema/flag change (D-04) — all locked per CONTEXT.md, approved 2026-08-19"
  - "Floor-to-cent quantization uses a 1e-9 epsilon subtracted before flooring to absorb float64 boundary-exact representation error (see Deviations)"
metrics:
  duration: ~25m
  completed: 2026-08-19
---

# Quick Task 260819-g5h: Add minimum stop distance floor to targets.py stop engine Summary

Added a 0.5x ATR minimum stop-distance floor to the stop engine in `scanner/targets.py` via a new `apply_min_stop_floor()` pure helper, wired into `attach_risk()` after the existing stop-above-entry guard and before `compute_targets()`.

## What Was Built

- **`MIN_STOP_ATR_MULT = 0.5`** — module constant, house rule, not tuned to backtest expectancy (D-01).
- **`apply_min_stop_floor(stop, price, atr, mult=MIN_STOP_ATR_MULT)`** — total pure function. Coerces inputs to float inside a `try`, returns the input `stop` unchanged on any non-numeric/non-finite/non-positive-ATR input (no exception ever raised). Computes `price - mult * atr`, floors to the cent, and returns `min(stop, floor_candidate)` — this can only widen, never tighten (D-02).
- **Call site in `attach_risk`** — placed AFTER the existing `if stop >= price:` early return and BEFORE `compute_targets(...)`, so the stop-above-entry contract is unchanged and the floored stop feeds `risk_reward`.
- **Regression tests** in `tests/test_targets.py`: EPAC case, GNW case, never-tightens property, degenerate-ATR parametrize (0/negative/NaN/None), quantization invariant, breakout-floor-applied integration test, and guard-order-preserved integration test.

## Commits

- `57bc926` — feat(quick-260819-g5h): add 0.5x ATR minimum stop-distance floor to attach_risk
- `1630877` — test(quick-260819-g5h): pin EPAC/GNW regressions and guard-order contract for stop floor
- `f3596ae` — fix(quick-260819-g5h): reconcile test_stop_formula_breakout with floored stop

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Floor-to-cent alone did not satisfy the strict invariant under float64 boundary cases**
- **Found during:** Task 1 verification (`python -c` acceptance check for the GNW case)
- **Issue:** The plan specified `floor_candidate = math.floor(value * 100) / 100`. For the GNW case (price=7.30, atr=0.20, mult=0.5), the mathematically exact boundary `price - mult*atr = 7.20` is not exactly representable in float64 the way the *comparison* `price - result >= mult * atr` needs it to be: `7.30 - 7.20` evaluates to `0.09999999999999964` in Python float arithmetic, which is strictly less than `0.10`. A plain floor-to-cent landed exactly on this boundary and the invariant check (as specified verbatim in the plan's own Task 1 `<verify>` block) failed.
- **Fix:** Subtract a `1e-9` epsilon from the raw value before flooring (`math.floor((raw_value - 1e-9) * 100) / 100`). This pushes boundary-exact cases down one additional cent, which stays within the D-02 contract (widening further is always allowed) and guarantees the invariant holds under float64 comparison in all tested cases. Documented inline in `scanner/targets.py` with the reasoning.
- **Files modified:** `scanner/targets.py`
- **Commit:** `57bc926` (part of the same Task 1 commit; the epsilon was added before the first commit was made, so no separate commit exists for this fix)

No other deviations. Tasks 2 and 3 executed exactly as specified.

## Changed Expectations

Exactly one pre-existing test expectation changed, as predicted in `prior_investigation` item 2 of the plan:

| Test | Before | After | Cause |
|---|---|---|---|
| `test_stop_formula_breakout` | Asserted `enriched.suggested_stop == round(high_20_prev - 0.5*atr_val, 2)` (raw formula, unfloored) | Asserted `enriched.suggested_stop == apply_min_stop_floor(raw_stop, res.close, atr_val)`, pinned to the exact value `46.0` | The standard `_make_df()` breakout fixture produces a raw stop distance of 0.243x ATR (price 46.1913, ATR 0.3764, raw stop 46.10) — inside the 0.5x ATR floor, so the floor binds and widens the stop from 46.10 to 46.00. The raw formula is kept visible in the test (both `raw_stop` and `apply_min_stop_floor` are computed explicitly) so the underlying stop rule stays readable; the assertion pins the exact floored value rather than a tolerance. |

Two other pre-existing tests were verified to remain byte-identical and green, per the plan's requirement:
- `test_stop_formula_pullback` — unmodified. Its fixture measures 4.413x ATR stop distance, well outside the floor, so it does not bind.
- `test_attach_risk_stop_above_entry_safe` — unmodified. Its assertions are non-strict (`is not None`); Task 2 added the strict companion test `test_attach_risk_stop_above_entry_guard_order_preserved` alongside it.

## Golden Master

`tests/golden/` is **unmodified** — confirmed via `git diff --stat -- tests/golden/` returning empty, and `python -m pytest -q tests/test_golden_master.py` passing (4/4). This is unaffected because:
1. None of the four golden fixtures (`pullback_qualifying.json`, `pullback_near_miss.json`, `breakout_qualifying.json`, and the fourth golden file) encode `suggested_stop`, `suggested_target`, `risk_reward`, or `atr` — their tracked key sets are gate/score fields only (`qualified`, `failed_gates`, `skipped_gates`, `gates_passed`, `gates_total`, `score`, and strategy-specific indicator fields).
2. `tests/test_golden_master.py` calls `pb.evaluate()` / `br.evaluate()` directly and never calls `attach_risk`, which is invoked only from `scanner/core.py:668` and `scanner/backtest.py:375`.
3. Therefore the floor cannot reach the golden-master code path, matching the finding recorded in the plan's `prior_investigation` item 1.

## Verification

- `pytest -q` — 330 passed, 0 failed, offline, full suite (includes web-unrelated tests; no `npm test`/`ng test` needed, no web-layer change).
- `git diff -- tests/golden/` — empty.
- `git diff --stat HEAD~2 HEAD -- scanner/` — touches only `scanner/targets.py`; no change to `store_db.py`, no `schema_version` bump, no gate threshold, no score formula (D-04 satisfied).
- `grep -n "datetime.now\|Timestamp.now\|yf\." scanner/targets.py` — no matches; no prohibited pattern introduced.
- EPAC (28.91/28.89/0.71) and GNW (7.30/7.29/0.20) both satisfy `price - floored_stop >= 0.5 * atr`, pinned by dedicated tests.
- Stop-above-entry guard order preserved: verified both via ad hoc script during Task 1 and the dedicated Task 2 integration test.

## Self-Check: PASSED

- `scanner/targets.py` — FOUND (modified, contains `MIN_STOP_ATR_MULT`, `apply_min_stop_floor`, call site in `attach_risk`)
- `tests/test_targets.py` — FOUND (modified, contains 8 new tests + 1 reconciled test)
- Commit `57bc926` — FOUND in `git log --oneline --all`
- Commit `1630877` — FOUND in `git log --oneline --all`
- Commit `f3596ae` — FOUND in `git log --oneline --all`
