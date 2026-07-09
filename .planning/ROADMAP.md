# Roadmap: TraderAssist

## Milestones

- ✅ **v1.0 Signal Quality** — Phases 1–4 (shipped 2026-07-02)
- 🚧 **v1.1 Weekly Seasonality Analyzer** — Phases 5–7 (in progress)

## Phases

<details>
<summary>✅ v1.0 Signal Quality (Phases 1–4) — SHIPPED 2026-07-02</summary>

- [x] Phase 1: Industry Classification + ETF Data Layer (2/2 plans) — completed 2026-07-01
- [x] Phase 2: Industry Momentum Computation + Schema v7 (2/2 plans) — completed 2026-07-01
- [x] Phase 3: Industry Display in CLI + Web UI (2/2 plans) — completed 2026-07-01
- [x] Phase 4: Winner/Loser Characteristic Analysis (2/2 plans) — completed 2026-07-01

Full details: [.planning/milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

### 🚧 v1.1 Weekly Seasonality Analyzer (In Progress)

**Milestone Goal:** Add a standalone CLI tool (`seasonality_by_week.py`) that tests whether stocks in a given GICS sector show statistically significant calendar-week seasonality, using a year-block bootstrap for honest confidence intervals. Diagnostic-only — no wiring into the nightly scan/backtest/UI pipeline, no schema changes.

- [x] **Phase 5: Sector Resolution & Data Input** - Resolve a sector's tickers via a persisted cache and gather validated daily history ready for analysis (completed 2026-07-09)
- [ ] **Phase 6: Seasonality Statistics & Verification** - Per-week bootstrap statistics with CI-based significance flagging, proven on synthetic data
- [ ] **Phase 7: CLI Output & Reporting** - Table, interpretive summary, survivorship warning, and optional CSV export

## Phase Details

### Phase 5: Sector Resolution & Data Input

**Goal**: The CLI accepts a sector + universe and produces a validated set of tickers with their cached daily OHLCV history, ready for seasonality analysis.
**Depends on**: Nothing new (first phase of v1.1; builds on existing `data_store` and `earnings_store` patterns)
**Requirements**: SEAS-01, SEAS-02, SEAS-03, SEAS-04, SEAS-05
**Success Criteria** (what must be TRUE):

  1. User runs `seasonality_by_week.py --sector Technology --universe sp500` and gets the Technology tickers back, matched case-insensitively via a persisted ticker→sector cache (new `scanner/sector_store.py`, Parquet-backed like `earnings_store.py`)
  2. Passing a sector name that matches no known GICS sector exits with a clear error listing all valid sector names, without running any analysis
  3. On a second run, sector classifications load from the Parquet cache without re-querying yfinance
  4. Tickers with under 2 years of history in the lookback window are skipped, and the skipped tickers plus a count are logged; a missing or corrupt cache file for one ticker is skipped and logged rather than aborting the run
  5. Daily adjusted-close history is read from the existing `data_store.get_history` cache, hitting yfinance only on a cache miss

**Plans**: 3/3 plans complete
**Wave 1**

- [x] 05-01-PLAN.md — scanner/sector_store.py: Parquet per-ticker GICS-sector cache (SEAS-01)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 05-02-PLAN.md — scanner/seasonality.py: sector validation + universe filter + history validation pipeline (SEAS-01..05)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 05-03-PLAN.md — seasonality_by_week.py: thin CLI entry point (SEAS-01, SEAS-02)

### Phase 6: Seasonality Statistics & Verification

**Goal**: The tool computes honest per-week seasonality statistics with year-block bootstrap confidence intervals and proves its detection accuracy against synthetic data.
**Depends on**: Phase 5
**Requirements**: SEAS-06, SEAS-07, SEAS-08, SEAS-09, SEAS-14, SEAS-15
**Success Criteria** (what must be TRUE):

  1. For each ISO calendar week 1–52 (week 53 merged into 52), the tool reports mean/median/std daily log return in bps, n_obs, and n_years
  2. Each week's mean daily return is expressed as a delta vs. the full-sample baseline mean daily return
  3. A year-block bootstrap (resampling whole years with replacement, preserving each year's full ticker-day cross-section) produces a 95% CI per week for the delta, reproducible via `--bootstrap-iters` and `--seed`
  4. A week is flagged significant only when its 95% CI excludes zero — no parameter tuning to manufacture significance
  5. Synthetic tests pass: an injected -30bps week-28 effect across all years causes week 28 to be flagged significant, and a pure-noise run flags roughly 0–3 of 52 weeks (≈5% false-positive expectation), never more

**Plans**: TBD

### Phase 7: CLI Output & Reporting

**Goal**: Results are presented to the user as a readable per-week table, an interpretive summary with anti-overfitting caveats, and an optional CSV export.
**Depends on**: Phase 6
**Requirements**: SEAS-10, SEAS-11, SEAS-12, SEAS-13
**Success Criteria** (what must be TRUE):

  1. The CLI prints a 52-row table sorted by week with columns week, mean_daily_ret_bps, delta_vs_baseline_bps, ci_low_bps, ci_high_bps, median_bps, n_obs, n_years, significant
  2. The CLI prints a summary showing the baseline mean, the significant weeks (or the explicit "none — no week deviates significantly from baseline" message), and the 5 highest/lowest weeks by delta with a multiple-comparison caveat
  3. A one-line survivorship-bias warning appears in the output header
  4. Passing `--output <path>` writes the results table to CSV, while stdout output still happens regardless

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 → 6 → 7

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Industry Classification + ETF Data Layer | v1.0 | 2/2 | Complete | 2026-07-01 |
| 2. Industry Momentum Computation + Schema v7 | v1.0 | 2/2 | Complete | 2026-07-01 |
| 3. Industry Display in CLI + Web UI | v1.0 | 2/2 | Complete | 2026-07-01 |
| 4. Winner/Loser Characteristic Analysis | v1.0 | 2/2 | Complete | 2026-07-01 |
| 5. Sector Resolution & Data Input | v1.1 | 3/3 | Complete   | 2026-07-09 |
| 6. Seasonality Statistics & Verification | v1.1 | 0/TBD | Not started | - |
| 7. CLI Output & Reporting | v1.1 | 0/TBD | Not started | - |
