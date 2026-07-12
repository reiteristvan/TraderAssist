# Retrospective — TraderAssist

## Milestone: v1.0 Signal Quality

**Shipped:** 2026-07-02
**Phases:** 4 | **Plans:** 8 | **Timeline:** 2026-06-30 → 2026-07-02 (3 days)

### What Was Built

- INDUSTRY_ETF_MAP (50+ entries) + `resolve_industry_etf()` two-tier lookup — industry ETF classification foundation
- `_industry_strength()` + schema v9 — 20-day momentum, 50-MA flag, rank percentile on every signal with per-day look-ahead-free ETF anchoring
- CLI Industry/Mom/Trend/Rank% columns + Angular candidates table momentum columns with color coding and trend arrows
- Pre-registered 6-metric winner/loser analysis in backtest reports (WL_FEATURES constant, per-strategy tables, suppression/abort guards) + Angular W/L analysis cards in backtest detail page

### What Worked

- **Wave-based parallelization** — phases with independent file scopes (03-01 CLI + 03-02 UI) executed in parallel and never conflicted
- **TDD for data layer** — RED/GREEN cycle on `resolve_industry_etf()` and `QualityInfo` fields caught edge cases (None vs NaN, sector fallback) before any scan ran
- **Pre-registration pattern** — committing `WL_FEATURES` constant before viewing any backtest output cleanly satisfies the anti-cherry-picking requirement; zero debate, zero rework
- **Code review before milestone close** — 12 findings fixed, including one that would have caused a runtime crash (JSON.parse on malformed SQLite data) and one data-correctness bug (signal key collision in dual-strategy runs)
- **Existing patterns reused** — `_sector_strength()` template, `ALTER TABLE ADD COLUMN` migration precedent, `gate_detail_json` passthrough pattern all made new work straightforward

### What Was Inefficient

- **Schema version naming** — milestone planned "schema v7" but actual DB was already at v8; discovered at execution time; correct version (v9) applied but planning artifact still says "v7". Better: query `PRAGMA user_version` in the research phase.
- **API endpoint mismatch in UAT** — UAT test description listed `/api/runs/<run_id>/report` but correct endpoint is `/api/runs/<run_id>`; caught by user during UAT. Document the actual endpoint in UI-SPEC.
- **No pre-Phase-4 data for UI UAT** — all existing backtest runs predate Phase 4; user had to run a fresh backtest to verify the W/L cards. For features that depend on specific data shapes, include a seeded test fixture or a "generate test data" step in the plan.

### Patterns Established

- **`WL_FEATURES` pre-registration** — for any future analysis feature, define the feature list as a named constant in source code before running any analysis to prevent multiple-comparisons overfitting
- **Per-day ETF anchoring in backtests** — compute the ETF momentum dict once per calendar day (not per ticker per day) before entering the ticker sub-loop; reuse `day_ind_cache`
- **3-tuple signal key `(date, ticker, strategy)`** — use this pattern in any dict that indexes signals in mixed-strategy backtests to prevent key collisions
- **Integer-equality checks for 0/1 boolean columns** — `== 1` not `is True` or `truthy` for columns that hold SQLite integer booleans
- **`pd.isna()` guard before `bool()` coercion** — `bool(NaN)` evaluates to `True`; always check isna() first for any float field that may be NaN before warm-up window

### Key Lessons

- The evidence-first discipline (display-only → backtest → then consider gate) is working; v1.0 built the instrumentation needed to generate that evidence in v2
- Code review as a mandatory phase gate (not optional) caught two bugs that unit tests wouldn't catch: a crash on real DB data and a data-correctness bug in dual-strategy analysis
- The UAT workflow is efficient — 8 tests in under 10 minutes with the conversational one-at-a-time format
- Schema version tracking needs a machine-readable check in the research step, not a manual assumption

### Cost Observations

- Execution model: Sonnet 4.6 (all phases)
- Total sessions: ~10 background sessions across 3 days
- Context efficiency: MemPalace observation chain maintained continuity across context resets

---

## Milestone: v1.1 Weekly Seasonality Analyzer

**Shipped:** 2026-07-12
**Phases:** 3 | **Plans:** 8 | **Timeline:** 2026-07-09 → 2026-07-12 (phase execution, ~3 days)

### What Was Built

- `scanner/sector_store.py` — Parquet-backed ticker→GICS-sector cache, structurally mirroring `earnings_store.py`'s fetch/cache/sentinel pattern
- `scanner/seasonality.py` sector/universe resolution + `validate_history` (≥2yr admission, skip-not-fail semantics, reuses `data_store.get_history`)
- ISO-week log-return panel, per-week observed stats, and a vectorized numpy year-block bootstrap producing reproducible 95% CIs (`--bootstrap-iters`/`--seed`)
- Significance flagging (CI excludes zero, no tuning) with a synthetic-data test suite proving both true-positive detection (injected -30bps week-28 effect) and a bounded false-positive rate (0-3/52 on pure noise)
- CLI presentation layer: 52-row table, interpretive summary with multiple-comparison caveat, survivorship-bias warning, optional CSV export — `seasonality_by_week.py` as a thin entry point mirroring `scan.py`'s conventions

### What Worked

- **Goal-backward verification caught a real platform bug tests missed** — Phase 7's `gsd-verifier` ran the actual CLI against real cached data (not just `capsys`-mocked tests) and found a `UnicodeEncodeError` crash on Windows cp1252 streams that all 319 passing pytest tests were structurally blind to. This is exactly the class of gap "verify behaviorally, not just structurally" exists to catch.
- **Quick-task fix-and-reverify loop closed the gap fast** — `/gsd-quick` planned and executed a scoped 2-task fix (ASCII-safe print + a genuine non-`capsys` subprocess regression test) in ~10 minutes, then re-verification confirmed the exact prior-failing repro scenario now passes, with zero scope creep into unrelated code.
- **Code review before Phase 6 verification caught a silent-corruption BLOCKER** — `np.percentile` (not `nanpercentile`) on bootstrap draws was silently returning NaN + a false "not significant" for any week absent from even one resampled year. No exception, no warning — caught by code review, not by the original test suite, since no fixture constructed that exact edge case.
- **Diagnostic-only scoping discipline held** — the milestone explicitly stayed out of the scan/backtest/UI pipeline and schema, and every phase respected that boundary; zero scope creep across 3 phases.
- **Milestone-level integration check validated composition, not just isolated correctness** — even with all 3 phases individually verified `passed`, the integration checker still ran a live end-to-end CLI invocation to confirm Phase 5→6→7 actually compose into one working pipeline, catching a minor (non-blocking) log-count-vs-list-length mismatch in `validate_history` that no phase-level verification would have surfaced.

### What Was Inefficient

- **The Unicode bug shipped past phase execution and initial verification's first pass** — the root cause (a non-ASCII arrow character borrowed from an existing `scan.py` idiom) had already existed in the codebase for a prior milestone; it was copied into new code without anyone questioning whether it was platform-safe. A repo-wide "no non-ASCII in print() statements" lint or a CI job running on the actual target OS's default locale would have caught this before it reached verification at all.
- **`capsys`-based tests gave false confidence** — every CLI test in this milestone used `capsys`, which is structurally incapable of catching real stream-encoding bugs (it captures via an in-memory buffer that bypasses codec negotiation entirely). 319 passing tests said nothing about this failure mode. Any project targeting Windows should include at least one subprocess-based CLI test per entry point that runs without `capsys`.

### Patterns Established

- **Year-block bootstrap for cross-sectionally correlated panels** — resample whole years with replacement (not individual daily rows) when the underlying data has strong within-year cross-sectional correlation (e.g. all tickers in a sector moving together on any given day); naive row-level resampling understates uncertainty
- **`nanpercentile` + explicit insufficient-data flag, not bare `percentile`, for any per-group bootstrap** — silent NaN propagation from `percentile` masks real "not significant" results with "we don't actually know" results; make the distinction an explicit column
- **Subprocess + `PYTHONIOENCODING` for stream-encoding regression tests** — `capsys` can never reproduce this class of bug; use `subprocess.run(..., env={"PYTHONIOENCODING": "cp1252"})` against a standalone (non-pytest-collected) helper script instead
- **ASCII-only CLI confirmation/status prints** — any `print()` destined for a real console (not just captured test output) should avoid non-ASCII characters entirely on this project, given its actual Windows/cp1252 deployment target

### Key Lessons

- Passing tests are not the same as a working CLI — behavioral, non-mocked verification against the actual deployment platform is what caught the one real regression this milestone shipped with
- A milestone-level integration audit is worth running even when every phase individually passed — it exercises the seams between phases, not just the phases themselves
- Fix-scope discipline (fixing exactly the reported gap, not adjacent code) kept the quick-task remediation fast and low-risk; the identical bug in `scan.py` was fixed too, but only because it was explicitly and narrowly called out as in-scope, not because the fix wandered there
- Diagnostic-only milestones (no schema bump, no pipeline wiring) are lower-risk to ship and easier to verify in isolation — worth defaulting to this shape for exploratory/investigative features before committing to gate promotion

### Cost Observations

- Execution model: Sonnet 5 (all phases + verification + integration check + audit)
- Total sessions: 1 continuous session (resumed from a prior session that completed Phase 7 execution)
- Notable: the Phase 7 verification → quick-task fix → re-verification → milestone audit → milestone close chain ran as one unbroken sequence of background subagent dispatches, with the orchestrating session never blocking on synchronous work

---

## Cross-Milestone Trends

| Milestone | Phases | Plans | Duration | Key Pattern |
|-----------|--------|-------|----------|-------------|
| v1.0 Signal Quality | 4 | 8 | 3 days | Wave parallelization, pre-registration pattern, TDD data layer |
| v1.1 Weekly Seasonality Analyzer | 3 | 8 | 3 days (phase execution) | Behavioral verification catches platform bugs structural checks miss; year-block bootstrap for correlated panels; diagnostic-only scoping discipline |
