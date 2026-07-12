---
phase: 06-seasonality-statistics-verification
reviewed: 2026-07-10T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - scanner/seasonality.py
  - seasonality_by_week.py
  - tests/test_seasonality.py
  - tests/test_seasonality_cli.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-07-10
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the Phase 6 statistics pipeline (`compute_log_returns`, `week_observed_stats`,
`check_thin_data`, `bootstrap_week_ci`, `compute_seasonality_stats`) and the CLI wiring in
`seasonality_by_week.py`, plus both test files. The vectorized year-block bootstrap algorithm
is correct in the dense-data case that all four test suites exercise (every week present in
every drawn year), and the significance rule, baseline-recompute-per-draw, and week-53
remapping all match their documented design decisions (D-01/D-02/D-04/D-05).

However, a genuine silent-corruption bug was found and reproduced: when an ISO week is present
in the panel overall but *absent from at least one distinct year* (a realistic scenario for
partial-history tickers, staggered admission dates, or a sector with few surviving tickers),
`bootstrap_week_ci` can silently emit `NaN` confidence bounds and `significant = False` for
that week with no error, warning, or flag — directly violating the project's own stated design
philosophy ("prefer being loud and honest ... over silently producing a number that looks like
a result but isn't statistically meaningful," 06-CONTEXT.md). None of the four existing test
fixtures (`_build_bootstrap_panel`, `_build_no_variance_panel`, `_synthetic_panel`, and the
hand-built panels in `test_seasonality.py`) construct a week that is missing from even one
year, so this path is completely untested. This is classified as the phase's one BLOCKER.

The planning-flagged ASVS V5 input-validation item (`--bootstrap-iters` must reject non-positive
values before array allocation) is correctly implemented — `bootstrap_week_ci` raises
`ValueError` on `iters <= 0` before any array is sized by `iters`. `--seed`, however, has no
explicit validation at all; a negative seed is only caught incidentally by
`numpy.random.default_rng`'s own internal check, which fires *after* `sum_mat`/`cnt_mat` have
already been allocated (bounded by data-derived `n_years`, not attacker input, so no DoS
follows) and surfaces a raw numpy message ("expected non-negative integer") rather than the
project's own descriptive-`ValueError` convention. This is a WARNING, not a BLOCKER, since it
still fails closed with exit code 2.

## Critical Issues

### CR-01: `bootstrap_week_ci` silently returns NaN CI / false "not significant" for weeks missing from any single year

**File:** `scanner/seasonality.py:298-358` (specifically 336-345)
**Issue:**
`sum_mat`/`cnt_mat` are built per `(year_idx, iso_week)`; any `(year, week)` combination with
zero observations is left at its `np.zeros` initial value. In the resampling step:

```python
resampled_sum = sum_mat[draw].sum(axis=1)
resampled_cnt = cnt_mat[draw].sum(axis=1)
with np.errstate(invalid="ignore", divide="ignore"):
    resampled_week_mean = resampled_sum / resampled_cnt
```

if a week is entirely absent from every year selected by a given bootstrap draw (which will
happen on *every* draw whenever that week is present in the underlying panel but absent from at
least one distinct year — a realistic case for a ticker admitted mid-history, a staggered IPO,
or a small sector with only a few surviving tickers), `resampled_cnt` for that week is `0` on
every iteration, making `resampled_week_mean` (and therefore `delta`) `NaN` for every iteration.
`np.percentile` on an all-NaN column silently returns `NaN`, and
`significant = (ci_low > 0) | (ci_high < 0)` silently evaluates to `False` for `NaN` comparisons
— no exception, no warning, no sentinel value. The output is a perfectly normal-looking row
(`ci_low_bps = NaN, ci_high_bps = NaN, significant = False`) with no indication the CI is
meaningless. Reproduced directly:

```python
# Week 5 present only in 1 of 5 years; weeks 6/7 present in all 5.
result = bootstrap_week_ci(panel, iters=2000, seed=1)
#   week  ci_low_bps  ci_high_bps  significant
#      5         NaN          NaN        False   <-- silent corruption
#      6         0.0          0.0        False
#      7         0.0          0.0        False
```

This directly contradicts the phase's own documented design principle (06-CONTEXT.md
`<specifics>`): "prefer being loud and honest (abort on thin data, deterministic reproducible
output) over silently producing a number that looks like a result but isn't statistically
meaningful." None of the four test fixtures used across `test_seasonality.py` construct a
week absent from even one year, so this path has zero test coverage today.

**Fix:** Either (a) raise/flag when any week has zero total observations for a drawn year-block
rather than silently dividing, or (b) mask NaN weeks out of the final result with an explicit
`insufficient-data` indicator so downstream consumers (Phase 7) can distinguish "not
significant" from "cannot compute a CI." A minimal fix using `np.nanpercentile` plus an explicit
flag:

```python
resampled_week_mean = np.where(
    resampled_cnt > 0, resampled_sum / np.where(resampled_cnt > 0, resampled_cnt, 1), np.nan
)
...
ci_low, ci_high = np.nanpercentile(delta, [2.5, 97.5], axis=0)
all_nan = np.all(np.isnan(delta), axis=0)
significant = ((ci_low > 0) | (ci_high < 0)) & ~all_nan
# and surface all_nan (e.g. as an `insufficient_years` column) rather than silently
# defaulting to significant=False
```
Add a test with a week present in the panel but missing from at least one distinct year to
lock in the fixed behavior.

## Warnings

### WR-01: `--seed` has no explicit input validation despite being named alongside `--bootstrap-iters` in the phase's ASVS V5 control

**File:** `scanner/seasonality.py:298-313`; `seasonality_by_week.py:53-56`
**Issue:** 06-RESEARCH.md's Security Domain section (`V5 Input Validation`) flags both
`--bootstrap-iters` and `--seed` as "user-supplied CLI ints" requiring validation. Only `iters`
gets an explicit `if iters <= 0: raise ValueError(...)` check (line 312-313). `seed` is passed
straight through to `np.random.default_rng(seed)` with no project-level check; a negative seed
only fails because numpy's own constructor rejects it, producing an unrelated raw message
(`expected non-negative integer`) instead of the project's descriptive-`ValueError` convention
used everywhere else in this module (`resolve_sector`, `universe_path`, `check_thin_data`,
`iters` above). It still exits cleanly (caught by the CLI's `except ValueError` and returned as
exit code 2), so this is not a crash/DoS risk, just an inconsistent validation surface and a
worse error message for the user.
**Fix:**
```python
if seed < 0:
    raise ValueError(f"seed must be a non-negative integer, got {seed}")
```
placed alongside the existing `iters <= 0` check in `bootstrap_week_ci`, before `sum_mat`/
`cnt_mat` are allocated, for consistency with the rest of the module's validation style.

### WR-02: No upper bound on `--bootstrap-iters` — arbitrarily large values allocate unbounded memory instead of failing with a clear error

**File:** `scanner/seasonality.py:298-334`
**Issue:** `bootstrap_week_ci` only rejects `iters <= 0`; there is no ceiling. `draw = rng.integers(0, n_years, size=(iters, n_years))` and the subsequent `(iters, 52)`-shaped
`resampled_sum`/`resampled_cnt`/`delta` arrays scale directly with `iters`. A large or
typo'd value (e.g. `--bootstrap-iters 100000000000`) will attempt a multi-terabyte allocation
and crash with an unhandled `MemoryError`/`numpy.core._exceptions._ArrayMemoryError` rather than
the clean `ValueError`-with-message path the rest of the CLI uses. 06-RESEARCH.md's threat
analysis (T-6-01) explicitly scoped this to "non-positive" only and treated it as an accepted
risk, but the failure mode (uncaught `MemoryError` crashing the process with a stack trace
instead of exit code 2 + stderr message) is inconsistent with every other validation path in
this module.
**Fix:** Add a documented sane ceiling, e.g.:
```python
_MAX_BOOTSTRAP_ITERS = 100_000
...
if iters <= 0 or iters > _MAX_BOOTSTRAP_ITERS:
    raise ValueError(
        f"bootstrap-iters must be between 1 and {_MAX_BOOTSTRAP_ITERS}, got {iters}"
    )
```

### WR-03: `compute_log_returns` drops leading NaN but not `-inf`/`inf` from non-positive Close prices

**File:** `scanner/seasonality.py:220-237`
**Issue:** `log_ret_bps = np.log(df["Close"]).diff() * 10_000` produces `-inf` (not `NaN`) if any
`Close` value is `0` or negative, and `inf`/`NaN` if the *following* row's Close is 0. The
subsequent `part.dropna(subset=["log_ret_bps"])` only drops `NaN` rows, so a bad zero/negative
`Close` value anywhere in a cached OHLCV frame would inject `-inf`/`inf` into the panel, silently
corrupting `week_observed_stats`'s mean/median/std and `bootstrap_week_ci`'s CI for every week
that ticker-day belongs to (an `inf` in a `sum` poisons every subsequent aggregate derived from
it). This relies entirely on `data_store.get_history`'s upstream data being well-formed; there is
no defensive check in this module. Low likelihood given the data source, but the failure mode if
triggered (silent, unbounded corruption of every downstream statistic, not just the offending
row) is disproportionate to the missing one-line guard.
**Fix:**
```python
log_ret_bps = np.log(df["Close"]).diff() * 10_000
log_ret_bps = log_ret_bps.replace([np.inf, -np.inf], np.nan)
...
part = part.dropna(subset=["log_ret_bps"])  # now also drops inf-derived rows
```

## Info

### IN-01: `week_observed_stats`'s `std_bps` uses pandas' default `ddof=1`, producing `NaN` for any week with exactly one observation

**File:** `scanner/seasonality.py:255-260`
**Issue:** `.agg(std_bps="std")` on a single-row group returns `NaN` (sample std with `ddof=1`
needs >=2 points). This is unlikely at production scale (multi-ticker, multi-year panels) but
is a hidden edge case worth documenting since `std_bps` is exported through `SeasonalityResult`
for Phase 7 to consume; a `NaN` there could propagate into a rendered table without explanation.
**Fix:** Either accept and document the `NaN` (Phase 7's concern to render), or use
`std_bps=("log_ret_bps", lambda s: s.std(ddof=0) if len(s) > 1 else 0.0)` if a defined value is
preferred over `NaN` for single-observation weeks.

### IN-02: `SectorDataset.universe` normalization is inconsistent between `load_sector_dataset` and ad-hoc callers

**File:** `scanner/seasonality.py:200`; `tests/test_seasonality.py:517`; `tests/test_seasonality_cli.py:47`
**Issue:** `load_sector_dataset` always lower-cases `universe` (`universe=universe.lower()`), but
`SectorDataset` is also constructed directly in tests (and could be constructed directly by any
future caller) with an un-normalized value (e.g. `universe="sp500"` is fine, but nothing enforces
the invariant at the dataclass level — it's purely a convention followed by one constructor call
site). Not a bug today (no code currently branches on `universe`'s case), but worth flagging as
a latent inconsistency if a future consumer starts comparing `dataset.universe` against a
lower-case literal.
**Fix:** Low priority — no action required unless a future phase starts branching on
`SectorDataset.universe`'s case.

---

_Reviewed: 2026-07-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
