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

## Cross-Milestone Trends

| Milestone | Phases | Plans | Duration | Key Pattern |
|-----------|--------|-------|----------|-------------|
| v1.0 Signal Quality | 4 | 8 | 3 days | Wave parallelization, pre-registration pattern, TDD data layer |
