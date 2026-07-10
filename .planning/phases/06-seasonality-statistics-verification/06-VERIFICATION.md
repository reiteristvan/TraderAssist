---
phase: 06-seasonality-statistics-verification
verified: 2026-07-10T13:00:00Z
status: passed
score: 16/16 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 6: Seasonality Statistics & Verification Verification Report

**Phase Goal:** The tool computes honest per-week seasonality statistics with year-block bootstrap confidence intervals and proves its detection accuracy against synthetic data.
**Verified:** 2026-07-10
**Status:** passed
**Re-verification:** No — initial verification (post code-review-fix)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `compute_log_returns` pools every admitted ticker's daily log return into one ISO-tagged panel (week 53 → 52, leading NaN dropped) | VERIFIED | `scanner/seasonality.py:214-260`; uses `df.index.isocalendar()` for both year and week (never `.year`); `-inf`/`inf` from non-positive Close explicitly replaced with NaN before dropna (WR-03 fix, `seasonality.py:237`) |
| 2 | `week_observed_stats` returns one row per observed week with mean/median/std/n_obs/n_years | VERIFIED | `scanner/seasonality.py:263-294`; columns exactly `[week, mean_daily_ret_bps, median_bps, std_bps, n_obs, n_years, delta_vs_baseline_bps]`; tests `test_week_observed_stats_columns_exact` et al. pass |
| 3 | Each week's delta vs. pooled full-sample baseline (SEAS-07) | VERIFIED | `scanner/seasonality.py:271,280`; baseline = flat `panel["log_ret_bps"].mean()`, not per-week average; `test_week_observed_stats_baseline_delta_matches_plan_hand_computed_example` passes |
| 4 | `check_thin_data` aborts (ValueError) below 5 distinct ISO years, dataset-wide (D-05) | VERIFIED | `scanner/seasonality.py:297-313`; `test_check_thin_data_four_years_raises`/`five_years_returns_none`/`twenty_years_returns_none`/`dataset_wide_not_per_ticker` pass |
| 5 | `bootstrap_week_ci` resamples whole years with replacement, baseline recomputed per iteration (D-02, Pitfall 4) | VERIFIED | `scanner/seasonality.py:316-419`, step `baseline_mean = resampled_sum.sum(axis=1) / resampled_cnt.sum(axis=1)` inside the per-iteration vectorized computation, not the fixed observed value |
| 6 | Same seed → identical CI; different seed → different CI (reproducibility) | VERIFIED | `numpy.random.default_rng(seed)` used (no legacy global seed); `test_bootstrap_ci_reproducible_same_seed` (uses `pd.testing.assert_frame_equal`) and `test_bootstrap_ci_different_seed_differs` pass |
| 7 | Significance = CI excludes zero, no tunable statistic (SEAS-09) | VERIFIED | `scanner/seasonality.py:405`: `significant = ((ci_low > 0) \| (ci_high < 0)) & ~insufficient_years`; `test_bootstrap_ci_significance_rule` passes |
| 8 | `bootstrap_week_ci` raises ValueError on `iters <= 0` before array allocation (ASVS V5) | VERIFIED | `scanner/seasonality.py:346-349`, guard runs before `sum_mat`/`cnt_mat` allocation; `test_bootstrap_ci_iters_zero_raises`/`iters_negative_raises` pass |
| 9 | `compute_seasonality_stats` orchestrates all 4 stages into one `SeasonalityResult` (SEAS-08 assembly) | VERIFIED | `scanner/seasonality.py:422-478`: `compute_log_returns → check_thin_data → week_observed_stats → bootstrap_week_ci`, merged into the 9 SEAS-10 columns + `std_bps` + `insufficient_years`; 4 orchestrator unit tests pass |
| 10 | CLI wires `--bootstrap-iters`/`--seed` through; ValueError surfaces as exit 2 | VERIFIED | `seasonality_by_week.py:65-72` calls `compute_seasonality_stats` inside the existing `except ValueError` → `return 2` block; `test_main_thin_data_value_error_exits_2` passes |
| 11 | Synthetic injected -30bps week-28 effect flagged significant (SEAS-14) | VERIFIED | `test_synthetic_injected_week28_effect_flagged_significant` passes (20-year/15-ticker panel, real `compute_seasonality_stats` path, not a guard bypass) |
| 12 | Synthetic pure-noise run flags 0-3 of 52 weeks (SEAS-15) | VERIFIED | `test_synthetic_noise_flags_0_to_3_of_52` passes |
| 13 | **[Post-review fix] CR-01 BLOCKER resolved**: a week missing from ≥1 distinct year no longer silently returns NaN CI + `significant=False` indistinguishable from a real "not significant" | VERIFIED | `scanner/seasonality.py:374-419` replaced `np.percentile` with `np.nanpercentile` and added `insufficient_years` column, forced `significant=False` only when flagged; regression tests `test_bootstrap_ci_week_missing_from_one_year_no_longer_silently_nan` and `test_bootstrap_ci_week_never_drawn_flagged_insufficient_years` (commit f6b47ab) both pass and directly reproduce the review's exact failure scenario |
| 14 | **[Post-review fix] WR-01 resolved**: negative `--seed` raises descriptive ValueError | VERIFIED | `scanner/seasonality.py:350-351` (commit efbfcbf); `test_bootstrap_ci_seed_negative_raises`/`seed_zero_does_not_raise` pass |
| 15 | **[Post-review fix] WR-02 resolved**: `--bootstrap-iters` has an enforced upper ceiling (100,000) instead of unbounded MemoryError | VERIFIED | `scanner/seasonality.py:56,346-349` (commit a6cee4d); `test_bootstrap_ci_iters_above_ceiling_raises`/`iters_at_ceiling_does_not_raise` pass |
| 16 | **[Post-review fix] WR-03 resolved**: non-positive Close no longer injects `-inf`/`inf` into downstream aggregates | VERIFIED | `scanner/seasonality.py:237` (commit 660402f); `test_compute_log_returns_zero_close_drops_inf_not_poisons_panel`/`negative_close_drops_inf_not_poisons_panel` pass |

**Score:** 16/16 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scanner/seasonality.py` | Phase 6 statistics pipeline (compute_log_returns, week_observed_stats, check_thin_data, bootstrap_week_ci, compute_seasonality_stats) plus CR-01/WR-01/WR-02/WR-03 fixes | VERIFIED | All functions present, substantive (no stubs), and wired into `compute_seasonality_stats`; review-fix commits confirmed landed (f6b47ab, efbfcbf, a6cee4d, 660402f) |
| `seasonality_by_week.py` | Live `--bootstrap-iters`/`--seed` CLI wiring | VERIFIED | `main()` calls `compute_seasonality_stats`, help text no longer says "not used yet" for iters/seed (only `--output` retains placeholder wording, correctly deferred to Phase 7 per SEAS-13) |
| `tests/test_seasonality.py` | Unit + synthetic verification tests | VERIFIED | 46 test functions across compute_log_returns/week_observed_stats/check_thin_data/bootstrap_week_ci/compute_seasonality_stats/synthetic verification/CR-01-WR-01-02-03 regressions |
| `tests/test_seasonality_cli.py` | CLI wiring tests | VERIFIED | Includes `test_main_thin_data_value_error_exits_2` regression added in Plan 03 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `compute_log_returns` | `SectorDataset.frames` (Phase 5 output) | direct dict consumption | WIRED | `compute_seasonality_stats` calls `compute_log_returns(dataset.frames)` |
| `compute_log_returns`/`bootstrap_week_ci` | ISO year/week labels | `.isocalendar()` | WIRED | No `df.index.year` or wall-clock read anywhere in the module |
| `bootstrap_week_ci` | reproducible RNG | `numpy.random.default_rng(seed)` | WIRED | No legacy `np.random.seed(` call present |
| `seasonality_by_week.py::main` | `compute_seasonality_stats` | direct call inside try/except ValueError | WIRED | Confirmed at `seasonality_by_week.py:65-72`; exit code 2 on ValueError |
| `compute_seasonality_stats` | `week_observed_stats` + `bootstrap_week_ci` merge | inner join on `week` | WIRED | `scanner/seasonality.py:450` |

### Behavioral Spot-Checks / Probe Execution

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full pytest suite green after review-fix | `python -m pytest -q` | 295 passed, 2 expected RuntimeWarnings (log of non-positive Close in WR-03 test fixtures) | PASS — matches 06-REVIEW-FIX.md's claimed "295 passed" exactly |
| CR-01/WR-01/WR-02/WR-03 regression tests | `pytest -q tests/test_seasonality.py -k "bootstrap_ci_week_missing... or ...seed_negative_raises or ...iters_above_ceiling_raises or ...zero_close_drops_inf..."` (8 named tests) | 8 passed | PASS |
| SEAS-14/SEAS-15 synthetic tests | `pytest -q tests/test_seasonality.py -k "synthetic_injected or synthetic_noise"` | 2 passed | PASS |
| No debt markers in modified files | `grep -n -E "TBD\|FIXME\|XXX" scanner/seasonality.py seasonality_by_week.py tests/test_seasonality.py tests/test_seasonality_cli.py` | no matches | PASS |
| No placeholder/stub returns in `seasonality.py` | `grep -n -E "return None$\|return \{\}\|return \[\]" scanner/seasonality.py` | no matches | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|-------------|--------|----------|
| SEAS-06 | 06-01 | Per-week mean/median/std bps, n_obs, n_years, week 53 merged into 52 | SATISFIED | `week_observed_stats`, `compute_log_returns` + tests |
| SEAS-07 | 06-01 | Delta vs. full-sample baseline | SATISFIED | `week_observed_stats` + tests |
| SEAS-08 | 06-02, 06-03 | Year-block bootstrap 95% CI, `--bootstrap-iters`/`--seed` reproducibility | SATISFIED | `bootstrap_week_ci`, `check_thin_data`, CLI wiring + tests |
| SEAS-09 | 06-02 | Significance = CI excludes zero, no tuning | SATISFIED | `bootstrap_week_ci` significance rule + test |
| SEAS-14 | 06-03 | Synthetic injected -30bps week-28 effect flagged significant | SATISFIED | `test_synthetic_injected_week28_effect_flagged_significant` |
| SEAS-15 | 06-03 | Synthetic pure-noise flags 0-3/52 | SATISFIED | `test_synthetic_noise_flags_0_to_3_of_52` |

No orphaned requirements — REQUIREMENTS.md maps exactly SEAS-06/07/08/09/14/15 to Phase 6, and all six appear in the plans' `requirements` frontmatter and are marked `[x]` in REQUIREMENTS.md. SEAS-10 through SEAS-13 are correctly scoped to Phase 7 (Output), not this phase.

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers in any file modified by this phase. No stub returns (`return None`/`return {}`/`return []`) in production code beyond the legitimate empty-panel guard in `compute_log_returns` (`if not parts: return pd.DataFrame(columns=columns)`), which is correct defensive behavior, not a stub.

### Code Review Fix Verification (BLOCKER + 3 WARNINGs)

The 06-REVIEW.md BLOCKER (CR-01) and all 3 WARNINGs (WR-01/02/03) were independently re-verified against the actual code, not just the fix report's claims:

- **CR-01 (BLOCKER)**: Confirmed `np.percentile` → `np.nanpercentile` change at `scanner/seasonality.py:403`, `insufficient_years` column added and threaded through `compute_seasonality_stats`'s merged output, and `significant` is forced `False` only when `insufficient_years` is `True` (not silently defaulting via NaN comparison). Both regression tests reproduce the review's exact failure scenario (a week present overall but absent from ≥1 distinct year) and pass.
- **WR-01**: `seed < 0` guard confirmed present before RNG construction, with the module's own descriptive-ValueError convention (not numpy's raw message).
- **WR-02**: `_MAX_BOOTSTRAP_ITERS = 100_000` ceiling confirmed, applied in the same guard as the `iters <= 0` check, before any array allocation.
- **WR-03**: `.replace([np.inf, -np.inf], np.nan)` confirmed present immediately after `log_ret_bps` computation, before the leading-NaN dropna.

Full offline pytest suite re-run independently by this verifier: **295 passed**, 2 expected RuntimeWarnings — matching the fix report's claim exactly, not merely trusted from SUMMARY.md.

### Human Verification Required

None. All must-haves are programmatically verifiable (pure numeric transforms, deterministic seeded bootstrap, CLI exit codes) and were verified directly against the codebase and a live test run.

### Gaps Summary

No gaps. All 16 must-haves (12 phase-goal truths + 4 code-review-fix truths) are VERIFIED against actual code and a live, independently-run test suite (295 passed). The phase goal — honest per-week seasonality statistics with year-block bootstrap CIs, proven against synthetic data — is achieved, and the one BLOCKER found during code review (silent NaN-CI corruption for partial-history weeks) is confirmed fixed with real regression-test coverage, not just claimed.

---

_Verified: 2026-07-10T13:00:00Z_
_Verifier: Claude (gsd-verifier)_
