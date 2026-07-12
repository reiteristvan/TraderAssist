# Phase 6: Seasonality Statistics & Verification - Research

**Researched:** 2026-07-10
**Domain:** Statistical computing (bootstrap resampling) on pandas/numpy, extending an existing single-file pipeline module
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Pool ticker-days as the unit of observation for both the point estimate (mean/
  median/std per week) and the bootstrap resampling — every (ticker, trading-day) pair within
  a week is one equally-weighted data point. `n_obs` for a week = total ticker-days across all
  admitted tickers and all years. This means sectors/tickers with more surviving history
  contribute proportionally more observations; that tradeoff was chosen deliberately over
  computing a sector daily-average index first (which would equal-weight each day but shrink
  `n_obs` to just trading-days × years, discarding cross-sectional information).
- **D-02:** The year-block bootstrap resamples at the year level: each bootstrap iteration
  draws distinct years with replacement, and for each drawn year, ALL ticker-days from that
  year (across all tickers) move together as one block — this is what "preserving each year's
  full ticker-day cross-section" means operationally, and it's what makes the CI honest despite
  cross-sectional correlation within a sector on any given day.
- **D-03:** `--bootstrap-iters` defaults to `1000` when not passed.
- **D-04:** `--seed` defaults to a fixed value (e.g. `42`) when not passed — two unflagged runs
  must produce identical significance flags. This is a deliberate anti-cherry-picking choice:
  the milestone's whole premise is "no tuning to manufacture significance," so a non-
  deterministic default (re-running until a week looks significant) would undermine that. Exact
  default seed value is Claude's discretion at implementation time (42 was the example given,
  not a hard requirement).
- **D-05:** Before running the bootstrap, count the distinct calendar years present across the
  admitted dataset. If fewer than **5 distinct years**, abort with a clear error rather than
  computing a CI on too few resampling blocks. This guard applies to the whole dataset (all
  admitted tickers combined), not per-ticker. It interacts with `--years`: if a shorter `--years`
  window collapses the distinct-year count below 5, the guard still fires. Exact abort behavior
  (exit code, message format) should mirror Phase 5's `resolve_sector` / `universe_path`
  `ValueError`-with-message pattern — Claude's discretion.
- **D-06:** Both synthetic tests (injected-effect detection and pure-noise false-positive rate)
  run as a **single fixed-seed run each** — deterministic, fast, no statistical-distribution
  assertions across multiple trials. Pick/verify a seed where the noise scenario's flagged
  count reliably lands in the 0-3 range before locking it into the test. Synthetic dataset
  construction (years, tickers, noise distribution, injection mechanism) is Claude's discretion,
  informed by D-05's 5-year minimum — the synthetic dataset must itself satisfy the thin-data
  guard (>=5 distinct years) to exercise the real code path end-to-end.

### Claude's Discretion

- CI construction method (percentile bootstrap is the natural fit given "no tuning" — simplest,
  most transparent, no distributional assumptions; confirmed during this research — see Standard
  Stack — no BCa/normal-approximation complexity needed).
- Exact function names/signatures added to `scanner/seasonality.py` for week-aggregation,
  baseline delta, bootstrap CI, and significance flagging.
- Log-return formula details (e.g., `np.log(close_t / close_{t-1})`) and where NaN/gap days
  within a ticker's series get dropped vs handled.
- Exact default seed value (42 given as an example, not locked).
- Synthetic test dataset size/shape (years, ticker count, noise model).

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. Out-of-scope items carried from the phase boundary:
CLI table/summary rendering, CSV export, survivorship-bias warning text (Phase 7); any change to
Phase 5's data-loading pipeline beyond extending the same module; multiple-comparison correction
(Bonferroni/FDR) across the 52 weekly tests — explicitly not wanted; wiring into scan/backtest
pipeline or schema changes.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| SEAS-06 | Daily log returns aggregated by ISO calendar week (1-52, week 53 merged into 52), reporting mean/median/std daily return (bps), n_obs, n_years per week | `compute_log_returns()` + `week_observed_stats()` — Pattern 1 (ISO week/year extraction, verified week-53 remap), Pitfall 1 |
| SEAS-07 | Each week's mean daily return reported as a delta vs. the full-sample baseline mean daily return | `baseline_mean_bps = panel["log_ret_bps"].mean()`; `delta_bps` column — Architecture Patterns diagram |
| SEAS-08 | Year-block bootstrap (resample years with replacement, preserving each year's full ticker-day cross-section) produces a 95% CI per week, controlled by `--bootstrap-iters`/`--seed`, reproducible; thin-data guard (D-05) aborts below 5 distinct years | `bootstrap_week_ci()` — Pattern 2 (verified vectorized algorithm, ~50ms/1000 iters), `check_thin_data()`, Pitfall 3 (small-blocks FP inflation), Pitfall 4 (baseline must be resampled, not fixed) |
| SEAS-09 | A week is flagged significant only when its 95% CI excludes zero — no tuning to manufacture significance | `significant = (ci_low > 0) \| (ci_high < 0)` — Standard Stack (percentile bootstrap chosen specifically to avoid a tunable test-statistic surface) |
| SEAS-14 | Synthetic test: injected -30bps week-28 effect across all years causes week 28 to be flagged significant | Code Examples — empirically verified parameters (20 years, 15 tickers, 150bps vol, data_seed=10) reliably flag week 28 (CI approx (-39.8, -24.1) bps) |
| SEAS-15 | Synthetic test: pure-noise run flags approximately 0-3 of 52 weeks, never more | Code Examples — same verified parameters give a stable 1-2/52 flagged count across 30 tested bootstrap seeds; Pitfall 3 explains why fewer years would be flaky |
</phase_requirements>

## Summary

Phase 6 adds four pure-computation stages to `scanner/seasonality.py`: (1) pool every admitted
ticker's daily log returns into a long panel tagged with ISO calendar year/week, (2) compute
observed per-week mean/median/std/n_obs/n_years plus a delta vs. the full-sample baseline mean,
(3) run a year-block percentile bootstrap to produce a 95% CI per week for that delta, and
(4) flag a week significant only when its CI excludes zero. No new third-party dependency is
required — `numpy` and `pandas` (already in `requirements.txt`) are sufficient; `scipy` is not
needed anywhere in this design (there is no hypothesis-test / p-value computation, only a
percentile-bootstrap CI and descriptive statistics, both of which `numpy.percentile` and
`pandas` groupby aggregations already provide).

The single riskiest design point — confirmed by directly prototyping and executing the
algorithm in this environment (see Code Examples) — is that **the year-block bootstrap's
false-positive rate is very sensitive to the number of distinct years available**, independent
of the number of tickers. With only 6-15 distinct years, pure-noise synthetic runs routinely
flagged 5-13 of 52 weeks as "significant" (far above the ~5%/2.6-week nominal expectation)
purely because so few resampling blocks exist. This is not a bug — it is the correct, honest
behavior of a small-block bootstrap — but it means D-05's "5-year minimum" is a validity floor,
not a value that itself guarantees SEAS-15's "0-3 of 52" expectation. For the phase's own
synthetic-verification tests, empirical search in this session found a stable, non-flaky
combination that satisfies both SEAS-14 and SEAS-15 simultaneously: **20 distinct years, 15
synthetic tickers, 150bps daily noise std, data-generation seed 10, bootstrap seed 42 (or any
of 30 tested alternate bootstrap seeds)** consistently flags 1-2/52 weeks under pure noise and
reliably detects an injected -30bps week-28 effect. This exact configuration is directly
reusable in the test suite.

**Primary recommendation:** Extend `scanner/seasonality.py` with a `compute_seasonality_stats()`
entry point built from four small functions (log-return panel construction, thin-data guard,
observed per-week stats, vectorized year-block bootstrap), using `pandas.DatetimeIndex.isocalendar()`
for week/year extraction and `numpy.random.default_rng(seed)` for reproducible resampling. Use
the precompute-a-sum/count-matrix-then-vectorize approach for the bootstrap (verified: ~50ms for
1000 iterations on a 78k-row synthetic panel) rather than a per-iteration pandas groupby loop.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ISO-week aggregation of daily log returns | CLI/Script (`scanner/seasonality.py`) | — | Diagnostic-only per PROJECT.md/REQUIREMENTS.md "Out of Scope" — no scan/backtest/API/UI wiring in this milestone |
| Delta-vs-baseline computation | CLI/Script (`scanner/seasonality.py`) | — | Same module, pure computation on the pooled panel |
| Year-block bootstrap CI | CLI/Script (`scanner/seasonality.py`) | — | Pure numpy/pandas computation, no persistence layer, no network I/O |
| Thin-data guard (abort path) | CLI/Script (`scanner/seasonality.py`) | CLI entry (`seasonality_by_week.py`) | `ValueError` raised in the module, caught and turned into exit code 2 at the thin CLI wrapper, mirroring Phase 5's pattern |
| Synthetic verification | Test suite (`tests/test_seasonality.py`) | — | pytest-only, no runtime component; must exercise the real code path (not a guard-bypassing shortcut) |

This milestone has exactly one active tier (the standalone script/engine layer). `web/api` and
`web/ui` are explicitly out of scope for the whole v1.1 milestone (REQUIREMENTS.md "Out of
Scope": "Web UI display of seasonality results").

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| pandas | 3.0.2 (installed) [VERIFIED: `python -c "import pandas; print(pandas.__version__)"` in this environment] | `DatetimeIndex.isocalendar()` for ISO year/week extraction, groupby aggregation for observed per-week stats | Already the project's dataframe library end-to-end; `.isocalendar()` is the built-in, correctness-tested way to get ISO year/week/day — confirmed empirically in this session that it correctly re-labels late-December/early-January dates into the adjacent ISO year (see Code Examples) |
| numpy | 2.4.4 (installed) [VERIFIED: same command] | `np.log` for log returns, `np.random.default_rng(seed)` for reproducible resampling, `np.percentile` for the bootstrap CI, vectorized fancy-indexing for the bootstrap loop | Already the project's numeric library; the modern `Generator` API (`default_rng`) is the numpy-recommended reproducible-RNG interface [CITED: numpy 2.4 docs via Context7, `/websites/numpy_doc_2_4`] |

### Supporting

None needed. `scipy.stats` is **not required** — confirmed not installed in this environment
(`ModuleNotFoundError: No module named 'scipy'`) [VERIFIED: `pip show scipy` in this environment]
and not needed by the design: the phase computes a percentile-bootstrap CI (order statistics via
`numpy.percentile`) and descriptive stats (mean/median/std via pandas groupby), neither of which
needs `scipy.stats`. No hypothesis test or p-value is part of the design (SEAS-09's significance
rule is purely "does the CI exclude zero"), so there is no place `scipy.stats.ttest`/`mannwhitneyu`
would be invoked in this phase's scope.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Percentile bootstrap CI (`numpy.percentile` on the resampled delta distribution) | BCa (bias-corrected and accelerated) bootstrap | BCa corrects for skew/bias but adds real implementation complexity (jackknife-based acceleration estimate) and is meaningfully slower; for a "no tuning to manufacture significance" design goal, the percentile method's simplicity and transparency is the better fit and is a standard, accepted method for this class of problem [CITED: Rousselet et al. 2021, "The Percentile Bootstrap: A Primer", journals.sagepub.com/doi/10.1177/2515245920911881 — practitioner literature confirms percentile bootstrap is standard for quantile/mean-difference inference, with BCa as a documented but heavier-weight alternative, "no method dominates"] |
| Precomputed (year × week) sum/count matrix + vectorized numpy resampling | Per-iteration `pandas.concat` + `groupby` on the raw ticker-day panel | The vectorized approach is mathematically identical (mean is a linear/decomposable statistic, so pre-aggregating sum and count per year-block before resampling reproduces the exact pooled-ticker-day mean) but avoids ~1000 repeated pandas concat/groupby calls; verified in this session that the vectorized approach completes 1000 iterations in ~50ms on a 78k-row synthetic panel [VERIFIED: direct execution in this environment] |
| `numpy.random.default_rng(seed)` (Generator API) | Legacy global `numpy.random.seed()` + `numpy.random.choice()` | The legacy global-state API is discouraged by numpy itself for new code; `default_rng` is self-contained (no global mutation risk if other code/tests also touch `np.random`) and is the API demonstrated in current numpy docs [CITED: numpy 2.4 docs via Context7] |

**Installation:** None required — no changes to `requirements.txt`.

**Version verification:** `pandas==3.0.2` and `numpy==2.4.4` confirmed installed via direct
execution in this environment; `pandas` 3.0.4 is the current latest per its own docs site
[CITED: pandas.pydata.org, fetched via Context7 `/websites/pandas_pydata_3_0_4`, "released on
June 28, 2026"] — the installed 3.0.2 is a recent patch behind but the `.isocalendar()` API used
here has been stable across all 3.0.x releases (it predates the 2.x→3.x transition entirely).
No version bump is needed or recommended for this phase.

## Package Legitimacy Audit

No new external packages are introduced by this phase. `pandas` and `numpy` are pre-existing
project dependencies (already in `requirements.txt`, already imported throughout `scanner/`).
The Package Legitimacy Gate protocol applies to *new* installs; since none are proposed here,
the audit is limited to confirming the existing pins are current and legitimate, which was done
via direct version checks above (not a registry-trust question — these are the project's
long-standing core dependencies).

**Packages removed due to `[SLOP]` verdict:** none (no new packages proposed)
**Packages flagged as suspicious `[SUS]`:** none

## Architecture Patterns

### System Architecture Diagram

```
SectorDataset.frames  (Phase 5 output: {ticker: DataFrame} — OHLCV, history-validated,
                        optionally --years-trimmed)
        │
        ▼
compute_log_returns(frames)
        │  pools every ticker's daily log return (Close_t / Close_{t-1}) into one long panel:
        │  columns [ticker, date, iso_year, iso_week, log_ret_bps]
        │  (week 53 remapped to 52 at this stage; first NaN row per ticker dropped)
        ▼
check_thin_data(panel)  ── raises ValueError if distinct iso_year count < 5 ──▶ caught by
        │                                                                       seasonality_by_week.py
        │  (else continue)                                                     main(), exit code 2
        ▼
        ├──▶ week_observed_stats(panel)  → mean_bps, median_bps, std_bps, n_obs, n_years  (per week)
        │
        ├──▶ baseline_mean_bps = panel["log_ret_bps"].mean()   (pooled full-sample baseline)
        │           │
        │           ▼
        │    delta_bps = week_mean_bps − baseline_mean_bps     (per week)
        │
        └──▶ bootstrap_week_ci(panel, iters, seed)
                  │  1. build (n_distinct_years × 52) sum/count matrix once
                  │  2. draw an (iters × n_years) matrix of year-indices via
                  │     rng.integers(0, n_years, size=(iters, n_years))
                  │  3. vectorized fancy-indexing sums reproduce each iteration's
                  │     resampled per-week mean AND resampled baseline mean
                  │  4. delta[iter, week] = resampled_week_mean − resampled_baseline_mean
                  │  5. ci_low/ci_high = np.percentile(delta, [2.5, 97.5], axis=0)
                  ▼
             significant = (ci_low > 0) | (ci_high < 0)
                  │
                  ▼
        SeasonalityResult(sector, universe, baseline_mean_bps, n_years,
                           bootstrap_iters, seed, weeks=<52-row DataFrame>)
                  │
                  ▼
        seasonality_by_week.py::main() — prints a plain dict/DataFrame summary for
        this phase's own manual verification (Phase 7 owns the polished table/CSV/summary)
```

### Recommended additions to `scanner/seasonality.py`
```
scanner/seasonality.py   (extend — do not create a new module, per CONTEXT.md canonical_refs)
├── _MIN_BOOTSTRAP_YEARS = 5          # module constant, separate from _MIN_HISTORY_DAYS
├── _DEFAULT_BOOTSTRAP_ITERS = 1000
├── _DEFAULT_SEED = 42
├── SeasonalityResult (dataclass)     # new — mirrors SectorDataset's dataclass-with-DataFrame shape
├── compute_log_returns(frames) -> pd.DataFrame
├── check_thin_data(panel, min_years=_MIN_BOOTSTRAP_YEARS) -> None
├── week_observed_stats(panel) -> pd.DataFrame
├── bootstrap_week_ci(panel, iters, seed) -> pd.DataFrame
└── compute_seasonality_stats(dataset, bootstrap_iters=..., seed=...) -> SeasonalityResult
```

### Pattern 1: ISO week/year extraction with week-53 merge
**What:** Use `DatetimeIndex.isocalendar()` (returns a DataFrame with `year`, `week`, `day`
columns) and remap week 53 to 52.
**When to use:** Once per ticker frame, immediately after computing log returns.
**Example:**
```python
# Source: pandas.pydata.org (Context7 /websites/pandas_pydata_3_0_4) +
# verified empirically in this environment (see below)
iso = df.index.isocalendar()
iso_week = iso["week"].where(iso["week"] != 53, 52)
iso_year = iso["year"]  # ISO year, NOT df.index.year — see Pitfall 2
```
Empirical confirmation that `.isocalendar()` correctly re-labels year-boundary dates (run in
this session):
```
2020-12-28  iso_year=2020  iso_week=53   (Gregorian date is still Dec 2020)
2019-12-30  iso_year=2020  iso_week=1    (Gregorian date is still Dec 2019, ISO year already 2020)
```

### Pattern 2: Reproducible year-block bootstrap via precomputed sufficient statistics
**What:** Since the week mean is a linear (sum/count) statistic, precompute a
`(n_distinct_years, 52)` matrix of `sum(log_ret_bps)` and `count` grouped by
`(iso_year, iso_week)` ONCE. Each bootstrap iteration then only needs to draw year-indices and
sum rows from this small matrix — no per-iteration DataFrame operations.
**When to use:** Any time the resampling unit (a "block") is coarser than the row granularity
being aggregated over multiple resamples of the same underlying data.
**Example:**
```python
# Source: verified via direct execution in this environment (prototype below)
years = np.sort(panel["iso_year"].unique())
n_years = len(years)
year_idx = panel["iso_year"].map({y: i for i, y in enumerate(years)})

sum_mat = np.zeros((n_years, 52))
cnt_mat = np.zeros((n_years, 52))
g = panel.assign(year_idx=year_idx).groupby(["year_idx", "iso_week"])["log_ret_bps"].agg(["sum", "count"])
for (yi, wk), row in g.iterrows():
    sum_mat[yi, wk - 1] = row["sum"]
    cnt_mat[yi, wk - 1] = row["count"]

rng = np.random.default_rng(seed)
draw = rng.integers(0, n_years, size=(iters, n_years))       # (iters, n_years)

resampled_sum = sum_mat[draw].sum(axis=1)                     # (iters, 52)
resampled_cnt = cnt_mat[draw].sum(axis=1)                     # (iters, 52)
resampled_week_mean = resampled_sum / resampled_cnt

baseline_mean = resampled_sum.sum(axis=1) / resampled_cnt.sum(axis=1)   # (iters,) — baseline is
                                                                          # ALSO resampled per
                                                                          # iteration (Pitfall 4)
delta = resampled_week_mean - baseline_mean[:, None]           # (iters, 52)
ci_low, ci_high = np.percentile(delta, [2.5, 97.5], axis=0)
significant = (ci_low > 0) | (ci_high < 0)
```
Verified runtime: **~50ms for 1000 iterations** on a synthetic 78,255-row panel (20 years × 15
tickers × ~261 business days/year) [VERIFIED: direct execution in this environment].

### Anti-Patterns to Avoid
- **Looping bootstrap iterations with `pd.concat` + `groupby` on the raw ticker-day panel:**
  functionally correct but does far more work than necessary per iteration; the sum/count
  matrix precompute (Pattern 2) is both simpler to reason about and much faster.
- **Holding the baseline fixed at the original observed value while only resampling week
  means:** understates the CI width because it ignores the baseline's own sampling variability;
  always recompute the baseline from the same resampled panel each iteration.
- **Using `df.index.year` instead of `df.index.isocalendar().year`** for year-block grouping:
  breaks the block/week correspondence near year boundaries (see Pitfall 2).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ISO calendar week/year numbering | Custom week-number math (day-of-year // 7, etc.) | `pandas.DatetimeIndex.isocalendar()` | ISO week-53 and year-boundary re-labeling rules are notoriously easy to get subtly wrong; pandas' implementation is standard-conformant and was verified in this session to correctly handle both boundary cases |
| Reproducible random resampling | Manual PRNG seeding via `random.seed()` / list shuffling | `numpy.random.default_rng(seed)` + `.integers(...)` | Numpy's modern `Generator` API is self-contained (no global state), documented as the recommended constructor, and is what the rest of the numeric stack expects |
| Percentile computation for the CI | Manual sort + index arithmetic for the 2.5th/97.5th percentile | `numpy.percentile(array, [2.5, 97.5], axis=0)` | Handles interpolation between order statistics correctly and is already vectorized across all 52 weeks in one call |

**Key insight:** Nothing in this phase needs a statistics library beyond numpy/pandas — the
temptation to reach for `scipy.stats` (e.g., for a "proper" hypothesis test) would work against
the explicit design goal (SEAS-09: pure CI-exclusion rule, no p-value/test-statistic tuning
surface to accidentally introduce cherry-picking).

## Common Pitfalls

### Pitfall 1: Week 53 left unmerged
**What goes wrong:** If the ISO week column isn't remapped, week 53 becomes an extra, nearly-empty
53rd bucket (occurs only in ISO leap-weeks, roughly 1 year in 5-6), silently breaking any code that
assumes exactly 52 weeks (e.g., preallocating a `(n_years, 52)` matrix, or Phase 7's fixed 52-row
table per SEAS-10).
**Why it happens:** `.isocalendar()` faithfully returns week 53 when the ISO calendar defines one;
merging it into 52 is a design decision (per CONTEXT.md), not something pandas does automatically.
**How to avoid:** Remap immediately after calling `.isocalendar()`: `week.where(week != 53, 52)`.
**Warning signs:** A 53rd row appearing in observed stats output, or an `IndexError`/silently-wrong
result if a fixed-size-52 matrix is indexed with a raw week value of 53.

### Pitfall 2: Using `df.index.year` instead of the ISO year for blocking
**What goes wrong:** A late-December trading day can belong to ISO week 1 of the *following* ISO
year (verified: `2019-12-30` → `iso_year=2020, iso_week=1`), while `df.index.year` would still say
2019. If week bucketing uses ISO year but year-block resampling uses calendar year (or vice
versa), a handful of days near each year boundary end up mis-blocked relative to their week label,
subtly corrupting the "each drawn year's full ticker-day cross-section moves together" guarantee
that D-02 depends on.
**Why it happens:** ISO year and Gregorian calendar year diverge for a small number of days near
every year boundary; `.isocalendar()` returns the ISO year, which is the one paired with the ISO
week number, but it's easy to instead pull `.year` from the DatetimeIndex directly out of habit.
**How to avoid:** Use `iso["year"]` (from the same `.isocalendar()` call) consistently for BOTH
week bucketing and year-block-bootstrap grouping — never mix ISO year with calendar year.
**Warning signs:** Off-by-one-year block membership for December/early-January dates; hard to spot
without an explicit boundary-date test.

### Pitfall 3: The 5-year floor (D-05) does not, by itself, guarantee a well-calibrated
false-positive rate
**What goes wrong:** Direct experimentation in this session showed that with only 6-15 distinct
years, a pure-noise synthetic dataset routinely flags 5-13 of 52 weeks as "significant" (well
above the ~5%/2.6-week nominal rate SEAS-15 expects), purely because the year-block bootstrap has
so few resampling blocks to draw from — this is expected/correct block-bootstrap behavior with a
small number of blocks, not a bug in the CI math. Increasing the number of tickers alone does
*not* fix this (verified: increasing tickers 10→100 with only 6 years still fluctuated between
5-11 flagged weeks) — only increasing the number of distinct years reliably tightens the CI toward
the nominal rate.
**Why it happens:** The year-block bootstrap's effective resampling diversity is bounded by the
number of distinct years, not the number of ticker-day observations within them; more tickers
reduce within-year noise but do not add resampling blocks.
**How to avoid:** Treat D-05's "5-year minimum" purely as a *validity floor* (below which running
a bootstrap at all is dishonest), not as a target that will itself produce a well-behaved
false-positive rate. For the phase's own SEAS-14/15 synthetic tests specifically, use enough
distinct years that the pure-noise scenario reliably lands in the 0-3/52 band — this session found
**20 distinct years** (well above the 5-year floor) gives a stable 1-2/52 flagged count across 30
different bootstrap seeds tested. Document this expectation for real (non-synthetic) sector runs
too: a sector dataset with only 5-6 years of history (the bare minimum to pass the guard) should be
expected to show an elevated false-positive rate versus the nominal ~5%, and that is an honest
property of the method, not a defect.
**Warning signs:** A synthetic pure-noise test that "usually" passes but occasionally flags 4-5+
weeks (flaky), especially if the synthetic dataset used only the guard's bare minimum (5-6 years).

### Pitfall 4: Recomputing the baseline outside the bootstrap loop
**What goes wrong:** If each bootstrap iteration reuses the ORIGINAL observed baseline (rather than
recomputing baseline from that iteration's own resampled panel), the resulting CI for the delta is
narrower than it should be — it fails to capture the baseline's own sampling variability, which
inflates the false-positive rate in the *other* direction (understating uncertainty, the exact
failure mode PROJECT.md calls out for naive daily resampling).
**Why it happens:** It's tempting to treat "baseline" as a fixed constant since it's reported once
in the observed-stats table; but for the bootstrap CI of the *delta*, both the week mean and the
baseline mean must be resampled together from the same year-block draw.
**How to avoid:** Compute `baseline_mean` fresh inside the vectorized bootstrap from the same
`resampled_sum`/`resampled_cnt` arrays used for the week means (see Pattern 2 code).
**Warning signs:** Bootstrap CIs that look implausibly tight compared to the observed std/n_obs for
a given week.

### Pitfall 5: Log returns across internal data gaps
**What goes wrong:** If a ticker's cached OHLCV has an internal gap (missing days not caught by
Phase 5's span-only `_MIN_HISTORY_DAYS` check), a simple `Close.diff()`/`shift()`-based log return
computes a "daily" return that actually spans multiple real trading days, attributing multi-day
drift entirely to whichever calendar week the later day falls in.
**Why it happens:** Phase 5's `validate_history` only checks the overall date span
(`(index.max() - index.min()).days >= 730`), not day-to-day contiguity within that span.
**How to avoid:** This is an accepted simplification for this phase (not a hard requirement to
fix — no SEAS requirement mandates gap detection/filling, and D-06 leaves "log-return formula
details ... and where NaN/gap days ... get dropped" to Claude's discretion). Recommend: compute
`np.log(close).diff()` per ticker, drop the resulting leading `NaN` (one row per ticker), and
explicitly document in a code comment that multi-day gaps are not specially handled — this keeps
the implementation simple and matches the "no tuning" ethos (no silent smoothing/interpolation
that could itself introduce bias). Flag as an `Assumptions Log` item so the planner/user can
decide if gap-detection deserves its own future ticket.
**Warning signs:** None in current code — this is a design choice to document, not a bug to catch.

### Pitfall 6: `datetime.now()` creeping into week/year bucketing
**What goes wrong:** CLAUDE.md's global convention bans wall-clock time in evaluation logic.
**Why it happens:** Easy to reach for "today" when deciding "what year is this" instead of reading
it from the data.
**How to avoid:** All year/week labels in this phase come from `df.index` /
`panel["date"]` — never from `date.today()`/`datetime.now()`. This falls out naturally from the
design above (everything is derived from `.isocalendar()` on the existing DataFrame index) but is
worth a one-line comment/assertion given the project-wide convention.
**Warning signs:** Any import of `datetime.now`/`pd.Timestamp.now` inside `scanner/seasonality.py`'s
new functions.

## Code Examples

### Empirically verified synthetic-test parameters (SEAS-14 / SEAS-15)
This exact configuration was found by scanning data-generation seeds 0-39 and bootstrap seeds
0-29 in this session, and is directly reusable in `tests/test_seasonality.py`:

```python
# Source: verified via direct execution in this environment this session.
# Recommended fixed parameters for the synthetic verification tests.
N_YEARS = 20          # comfortably above the 5-year D-05 floor; needed for a
                       # well-calibrated (not just "passing the guard") false-positive rate
N_TICKERS = 15
DAILY_VOL_BPS = 150    # ~1.5% daily stdev — realistic for individual equities
DATA_SEED = 10         # seeds the synthetic price-noise generator
BOOTSTRAP_SEED = 42    # the --seed default (D-04); tested stable across 30 alternate
                       # bootstrap seeds (0-29), pure-noise flagged count stayed in {1, 2}
BOOTSTRAP_ITERS = 1000 # the --bootstrap-iters default (D-03)

# Pure-noise test: build_panel(N_YEARS, N_TICKERS, ..., seed=DATA_SEED) with no injection
# → bootstrap flags 1-2 of 52 weeks (verified stable across 30 bootstrap seeds: min=1, max=2)

# Injected-effect test: same DATA_SEED, inject_week=28, inject_bps=-30.0
# → week 28's CI = approximately (-39.8, -24.1) bps, entirely below zero → flagged True
# → verified True across the tested candidate seeds, not just BOOTSTRAP_SEED=42
```
Full prototype (panel construction + vectorized bootstrap) used to derive and verify these
numbers is reproducible from Pattern 1 + Pattern 2 above combined with a synthetic-price
generator: for each of `N_TICKERS` synthetic tickers, draw
`rng.normal(0.0, DAILY_VOL_BPS, size=len(bdate_range))` as that ticker's daily log return series
in bps (no need to construct actual Close prices — only log returns are consumed downstream),
tag with `.isocalendar()` year/week, and for the injected-effect variant add `-30.0` to every
row where `iso_week == 28`.

### Log return computation (Pitfall 5)
```python
# Source: standard pattern, consistent with existing scanner/core.py float-returns style
log_ret = np.log(df["Close"]).diff()          # first row is NaN
log_ret_bps = (log_ret * 10_000).dropna()      # convert to bps, drop the leading NaN
```

## State of the Art

Not applicable in the "library deprecation" sense — this is new methodology for the codebase, not
an update to an existing pattern. The one relevant point: `numpy.random.RandomState` (legacy
global seeding) is officially superseded by the `Generator`/`default_rng` API for new code
[CITED: numpy 2.4 docs via Context7] — make sure no new code in this phase reaches for
`np.random.seed()`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Internal data gaps within an admitted ticker's history are not specially detected/handled — a `diff()`-based log return across a gap silently spans multiple real trading days | Common Pitfalls #5 | Low — no SEAS requirement mandates gap handling; if the user later observes a week's stats look distorted for a specific sector, gap detection could be added as a follow-up, but the simplification is defensible and consistent with "no silent smoothing" |
| A2 | 150bps (~1.5%) is a reasonable synthetic daily-volatility figure for individual-equity log returns, used only to construct the SEAS-14/15 test fixtures | Code Examples | Low — this only affects the synthetic test data's realism, not production behavior; any similar-magnitude value would work equally well as long as the seed search (already performed) is redone if changed |
| A3 | Real (non-synthetic) sector datasets with only 5-6 years of admitted history will show an elevated false-positive rate above the nominal ~5%, based on extrapolating the synthetic-noise experiment's pattern | Common Pitfalls #3 | Medium — this is inferred from experiments on synthetic i.i.d. data; real sector data has actual cross-sectional correlation and possibly genuine (not spurious) year-to-year variation, so the exact elevated-FP-rate magnitude for production sectors wasn't independently measured, only the qualitative direction (fewer years → less reliable CI) is established |

## Open Questions

1. **Should `week_observed_stats`'s std/median also be reported via the CLI in this phase, or only carried in the returned structure for Phase 7?**
   - What we know: SEAS-06 requires std to be part of the per-week statistics; SEAS-10 (Phase 7's table) does not list a `std_bps` column.
   - What's unclear: whether Phase 6's own manual-verification stdout print (mentioned in CONTEXT.md's code_context) needs to surface std, or whether it's enough that `SeasonalityResult.weeks` carries a `std_bps` column for Phase 7 to pick up later.
   - Recommendation: include `std_bps` in the returned DataFrame (satisfies SEAS-06 at the computation layer regardless of what stdout shows this phase); the planner should decide whether Phase 6's dev-facing print includes it — low-stakes either way since Phase 7 fully owns final rendering.

2. **Exact seed/dataset size the planner locks into the test — is 20 years/15 tickers acceptable "cost" for a fast test suite?**
   - What we know: the panel build + 1000-iteration bootstrap for this configuration ran in well under 200ms combined in this environment.
   - What's unclear: whether the planner prefers an even smaller dataset for speed at the cost of needing a fresh seed search (this session's search space was 0-39 for data seeds; smaller `n_years` configurations were tried and rejected for being too unstable/high-FP, not for being slow).
   - Recommendation: use the verified 20-year/15-ticker/seed-10 configuration as-is; it is already fast (no speed reason to shrink it), and shrinking risks reintroducing the small-blocks false-positive inflation documented in Pitfall 3.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| pandas | ISO week/year extraction, groupby stats | Yes | 3.0.2 | — |
| numpy | Log returns, RNG, percentile CI | Yes | 2.4.4 | — |
| scipy | Not required by this phase's design | N/A (not installed) | — | none needed |
| pytest | Synthetic verification tests | Yes | installed per `requirements.txt` | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none — `scipy` absence is not a gap, it's simply unneeded.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed; `pythonpath = ["."]` set in `pyproject.toml`, no other config) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest -q tests/test_seasonality.py` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEAS-06 | Per-week mean/median/std/n_obs/n_years computed correctly from a known synthetic panel | unit | `pytest -q tests/test_seasonality.py -k week_observed_stats -x` | ❌ Wave 0 (new test cases in existing `tests/test_seasonality.py`) |
| SEAS-07 | Delta vs. full-sample baseline computed correctly | unit | `pytest -q tests/test_seasonality.py -k baseline -x` | ❌ Wave 0 |
| SEAS-08 | Bootstrap CI reproducible across two runs with same `--seed`; distinct from a different seed | unit | `pytest -q tests/test_seasonality.py -k bootstrap_ci -x` | ❌ Wave 0 |
| SEAS-08 (thin-data guard, D-05) | `< 5` distinct years raises `ValueError` before computing a CI | unit | `pytest -q tests/test_seasonality.py -k thin_data -x` | ❌ Wave 0 |
| SEAS-09 | Significance flag is `True` iff CI excludes zero (boundary cases: CI touching zero exactly) | unit | `pytest -q tests/test_seasonality.py -k significant -x` | ❌ Wave 0 |
| SEAS-14 | Injected -30bps week-28 effect flags week 28 significant (fixed seed) | integration/synthetic | `pytest -q tests/test_seasonality.py -k synthetic_injected -x` | ❌ Wave 0 |
| SEAS-15 | Pure-noise run flags 0-3 of 52 weeks (fixed seed) | integration/synthetic | `pytest -q tests/test_seasonality.py -k synthetic_noise -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest -q tests/test_seasonality.py`
- **Per wave merge:** `pytest -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] New test functions in `tests/test_seasonality.py` covering SEAS-06/07/08/09/14/15 (file
      already exists from Phase 5 — this phase adds cases, doesn't create the file)
- [ ] No new fixtures/conftest needed — the existing `_synthetic_frame` helper pattern in
      `tests/test_seasonality.py` can be extended with a panel-building helper per the Code
      Examples section above
- [ ] No framework install needed — pytest already present

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Local diagnostic CLI, no auth surface |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | No multi-user access boundary |
| V5 Input Validation | Yes | `--bootstrap-iters` and `--seed` are user-supplied CLI ints; validate `--bootstrap-iters` is a positive integer before use (argparse `type=int` already rejects non-numeric input; add an explicit `> 0` check to avoid a zero/negative-size numpy array allocation) |
| V6 Cryptography | No | No cryptographic operation; `numpy.random.default_rng` is a statistical PRNG, not a security-sensitive one — reproducibility is the goal here, not unpredictability |

### Known Threat Patterns for this stack
No injection/network/auth threat surface — this phase is pure in-process numeric computation on
already-validated (Phase 5) local data. The only practical hardening item is guarding against a
degenerate `--bootstrap-iters 0` or negative value producing a malformed/empty result rather than
a clear error, which is a correctness concern more than a security one.

## Sources

### Primary (HIGH confidence)
- Direct execution in this environment (pandas 3.0.2 / numpy 2.4.4, Python 3.13.7) — verified
  `.isocalendar()` year-boundary behavior, verified the vectorized year-block bootstrap
  algorithm end-to-end, verified synthetic-test seed stability across 30 bootstrap seeds and
  40 data-generation seeds, verified runtime (~50ms/1000 iterations on a 78k-row panel)
- Context7 `/websites/pandas_pydata_3_0_4` — pandas latest-version confirmation
- Context7 `/websites/numpy_doc_2_4` — `numpy.random.default_rng`/`Generator.choice` API reference
- `scanner/seasonality.py`, `seasonality_by_week.py`, `tests/test_seasonality.py`,
  `tests/test_seasonality_cli.py` — existing Phase 5 code read directly

### Secondary (MEDIUM confidence)
- Rousselet, Pernet, Wilcox (2021), "The Percentile Bootstrap: A Primer With Step-by-Step
  Instructions in R" — journals.sagepub.com/doi/10.1177/2515245920911881 — percentile bootstrap
  standard-practice confirmation, found via WebSearch

### Tertiary (LOW confidence)
- None — all claims above were either verified via direct execution, cited from official docs,
  or explicitly logged in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack (numpy/pandas sufficiency, no scipy needed): HIGH — verified by direct
  execution and absence-of-scipy check in this exact environment
- Architecture (function decomposition, bootstrap algorithm): HIGH — the vectorized algorithm
  was prototyped and its output validated against expected behavior (injected effect detected,
  reproducibility confirmed) in this session
- Pitfalls (small-blocks false-positive inflation, ISO year vs. calendar year): HIGH — both were
  discovered and confirmed through direct experimentation in this session, not assumed from
  training knowledge
- Synthetic test parameters (SEAS-14/15): HIGH — empirically searched and stability-tested
  across 30+ seed combinations in this session

**Research date:** 2026-07-10
**Valid until:** 30 days (stable numeric-library APIs; no fast-moving dependency in this phase)
