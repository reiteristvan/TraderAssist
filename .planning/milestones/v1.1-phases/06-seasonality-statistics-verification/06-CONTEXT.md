# Phase 6: Seasonality Statistics & Verification - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 turns Phase 5's validated `{ticker: DataFrame}` dataset into honest per-week
seasonality statistics: daily log returns aggregated by ISO calendar week (1–52, week 53
merged into 52), a delta vs. full-sample baseline, a year-block bootstrap 95% CI per week,
and significance flagging (CI excludes zero, no tuning). It also proves the method works via
two synthetic-data tests — a known injected effect must be detected, and pure noise must stay
within the expected false-positive band.

**In scope:**
- ISO-week aggregation of daily log returns (mean/median/std in bps, n_obs, n_years per week)
- Delta vs. full-sample baseline mean daily return
- Year-block bootstrap (resample whole years with replacement, preserving each year's full
  ticker-day cross-section) producing a 95% CI per week, controlled by `--bootstrap-iters`
  and `--seed`
- Significance flag: CI excludes zero, no other criteria
- A thin-data guard that aborts before running the bootstrap when too few distinct years exist
- Synthetic-data tests proving true-positive detection (injected -30bps week-28 effect) and
  bounded false-positive rate (pure noise)

**Out of scope (deferred to Phase 7):**
- CLI table/summary rendering, CSV export, survivorship-bias warning text — Phase 7 consumes
  Phase 6's computed statistics but the presentation layer is not this phase
- Any change to Phase 5's data-loading pipeline (`scanner/seasonality.py`'s existing
  `load_sector_dataset`, `resolve_sector`, `validate_history`, etc.) beyond extending the same
  module with new functions
- Multiple-comparison correction (Bonferroni/FDR) across the 52 weekly tests — explicitly not
  wanted; SEAS-15's "~0-3 of 52 flagged on pure noise" expectation assumes an uncorrected ~5%
  per-week false-positive rate
- Wiring into scan/backtest pipeline or schema changes — out of scope for the whole milestone

</domain>

<decisions>
## Implementation Decisions

### Return Aggregation & Weighting
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

### Bootstrap Defaults & Reproducibility
- **D-03:** `--bootstrap-iters` defaults to `1000` when not passed.
- **D-04:** `--seed` defaults to a fixed value (e.g. `42`) when not passed — two unflagged runs
  must produce identical significance flags. This is a deliberate anti-cherry-picking choice:
  the milestone's whole premise is "no tuning to manufacture significance," so a non-
  deterministic default (re-running until a week looks significant) would undermine that. Exact
  default seed value is Claude's discretion at implementation time (42 was the example given,
  not a hard requirement).

### Thin-Data Guard
- **D-05:** Before running the bootstrap, count the distinct calendar years present across the
  admitted dataset. If fewer than **5 distinct years**, abort with a clear error rather than
  computing a CI on too few resampling blocks — a 2-3-year bootstrap is "noise dressed up as
  statistics," not an honest CI. This guard applies to the whole dataset (all admitted tickers
  combined), not per-ticker. It interacts with `--years`: if a shorter `--years` window is
  requested and it collapses the distinct-year count below 5, the guard still fires.
- Exact abort behavior (exit code, message format) should mirror Phase 5's `resolve_sector` /
  `universe_path` `ValueError`-with-message pattern for consistency — Claude's discretion.

### Synthetic Verification (SEAS-14/15)
- **D-06:** Both synthetic tests (injected-effect detection and pure-noise false-positive rate)
  run as a **single fixed-seed run each** — deterministic, fast, no statistical-distribution
  assertions across multiple trials. Pick/verify a seed where the noise scenario's flagged
  count reliably lands in the 0-3 range before locking it into the test, so the test isn't
  flaky on unlucky draws.
- Synthetic dataset construction (number of years, number of tickers, noise distribution used
  to generate synthetic price series, exact mechanism for injecting the -30bps week-28 effect)
  is Claude's discretion, informed by D-05's 5-year minimum — the synthetic dataset must itself
  satisfy the thin-data guard (>=5 distinct years) to exercise the real code path end-to-end
  rather than a guard-bypassing shortcut.

### Claude's Discretion
- CI construction method (percentile bootstrap is the natural fit given "no tuning" — simplest,
  most transparent, no distributional assumptions; confirm during research against the
  resampling design above, but no BCa/normal-approximation complexity expected to be needed)
- Exact function names/signatures added to `scanner/seasonality.py` for week-aggregation,
  baseline delta, bootstrap CI, and significance flagging
- Log-return formula details (e.g., `np.log(close_t / close_{t-1})`) and where NaN/gap days
  within a ticker's series get dropped vs handled
- Exact default seed value (42 given as an example, not locked)
- Synthetic test dataset size/shape (years, ticker count, noise model)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning & Requirements
- `.planning/ROADMAP.md` §Phase 6 — Goal, 5 success criteria, requirements mapping
  (SEAS-06, SEAS-07, SEAS-08, SEAS-09, SEAS-14, SEAS-15)
- `.planning/REQUIREMENTS.md` §Seasonality Statistics, §Verification — the six requirements
  mapped to Phase 6, with exact column/behavior wording
- `.planning/PROJECT.md` §Current Milestone — "year-block bootstrap for honest confidence
  intervals (not naive daily resampling, which understates uncertainty given cross-sectional
  correlation within a sector)" — the core methodological intent behind D-01/D-02
- `.planning/STATE.md` §Accumulated Context §Key Decisions — restates the year-block bootstrap
  and "no tuning to manufacture significance" decisions already locked pre-Phase-6

### Codebase Extension Points (patterns to mirror)
- `scanner/seasonality.py` — Phase 5's module; Phase 6 extends this SAME file (not a new
  module) per the D-04 precedent set in `05-CONTEXT.md` ("likely one `scanner/seasonality.py`
  module grown across all three phases"). `SectorDataset.frames` (`{ticker: DataFrame}`) is
  the direct input to Phase 6's week-aggregation function.
- `seasonality_by_week.py` — thin CLI at repo root; already declares `--bootstrap-iters` and
  `--seed` args (currently unused placeholders per its docstring) — Phase 6 is what makes them
  live. Follow the same thin-CLI-delegates-to-`scanner/`-module shape Phase 5 established.
- `scanner/seasonality.py::resolve_sector` / `::universe_path` — the `ValueError`-with-
  descriptive-message-then-CLI-catches-and-exits-2 pattern to mirror for the D-05 thin-data
  guard's abort path.
- `.planning/phases/05-sector-resolution-data-input/05-CONTEXT.md` — Phase 5's full context;
  read for the skip-not-fail philosophy, module-naming precedent, and history-validation
  details Phase 6's dataset already went through.

### Statistical Methodology
- No existing bootstrap/statistics code in this codebase (`scanner/report.py`'s
  `compute_metrics` is descriptive backtest metrics, not inferential statistics) — this is a
  new methodological pattern for the project. Confirm percentile-bootstrap CI construction
  against standard practice during research; `scipy.stats` is NOT currently in
  `requirements.txt` — decide during research/planning whether it's needed (e.g. for anything
  beyond percentile CIs) or whether `numpy`/`pandas` alone suffice (they should, for a
  percentile bootstrap).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scanner/seasonality.py::SectorDataset` — dataclass already carries `frames: dict[str,
  DataFrame]` (admitted tickers' OHLCV, already history-validated and optionally `--years`-
  trimmed) and `skipped` — Phase 6's stats function takes `SectorDataset.frames` as input.
- `seasonality_by_week.py::main` — already parses `--bootstrap-iters`/`--seed`/`--years` and
  calls `load_sector_dataset`; Phase 6 wires the real computation in after that call, still
  printing a stdout summary (full table/formatting is Phase 7, but Phase 6 needs SOME way to
  surface results for its own manual verification during development — likely a plain dict/
  DataFrame print, not the polished Phase 7 table).

### Established Patterns
- "SKIP, don't fail" for missing/ambiguous per-ticker data (Phase 5) vs. "abort the whole run"
  for the NEW thin-data guard (D-05) — these are different tiers: per-ticker gaps are
  tolerated, but a dataset-wide statistical validity problem (too few years) is not silently
  tolerated. Don't conflate the two philosophies.
- `_MIN_HISTORY_DAYS = 730` (2-year floor) already lives in `scanner/seasonality.py` — the new
  5-year distinct-years-for-bootstrap threshold (D-05) is a SEPARATE, higher bar checked after
  admission, not a replacement for the 2-year admission floor.
- No `datetime.now()` in evaluation logic (CLAUDE.md global convention) — any "current date"
  needed for week/year bucketing must come from the data's own index, not wall-clock time.

### Integration Points
- Phase 6 code lives in `scanner/seasonality.py` (extend, don't create a new module) and gets
  called from `seasonality_by_week.py::main` after `load_sector_dataset` returns.
- Phase 7 will import Phase 6's output (whatever return shape — likely a per-week
  DataFrame/list-of-dataclasses with the 9 SEAS-10 columns already computed) — Phase 6's
  function signatures/return types should be designed with that consumption in mind even
  though rendering itself is out of scope here.

</code_context>

<specifics>
## Specific Ideas

The user engaged directly with the statistical design (this milestone's PROJECT.md language
about "not naive daily resampling" originated from the user, not inferred) — treat the
methodology decisions above (D-01/D-02 pooling + year-block, D-05 thin-data guard, D-06
single-fixed-seed synthetic tests) as considered preferences, not defaults to revisit lightly.
The recurring theme across all four decisions: prefer being loud and honest (abort on thin
data, deterministic reproducible output) over silently producing a number that looks like a
result but isn't statistically meaningful.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 6-Seasonality Statistics & Verification*
*Context gathered: 2026-07-10*
