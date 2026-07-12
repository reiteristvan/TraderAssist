# TraderAssist

## What This Is

TraderAssist is a personal swing trading scanner that identifies pullback and breakout setups across S&P 400/500/600 universes. It runs nightly scans, generates signals with gate-based filtering, backtests strategies over historical data, and displays results through a web UI. Every signal now carries industry-group momentum context and backtest reports include a pre-registered winner/loser characteristic analysis. A standalone diagnostic CLI (`seasonality_by_week.py`) tests whether stocks in a given sector show statistically significant calendar-week seasonality, using a year-block bootstrap for honest confidence intervals. The owner uses it to surface actionable trade candidates with defined risk parameters and to systematically investigate whether entry-time context (industry momentum, entry RSI, RVOL, calendar-week seasonality) discriminates winners from losers.

## Core Value

Surface high-quality swing trade setups where the signal has a genuine edge — not just gate compliance.

## Current State

**Shipped:** v1.1 Weekly Seasonality Analyzer (2026-07-12)

v1.1 delivered `seasonality_by_week.py`, a standalone diagnostic CLI that tests whether stocks in a given GICS sector show statistically significant calendar-week seasonality using a year-block bootstrap (honest CI given cross-sectional correlation within a sector, unlike naive daily resampling). Diagnostic-only by design — no wiring into the nightly scan/backtest pipeline, no schema changes.

**Next milestone:** Not yet defined — run `/gsd-new-milestone` to scope v1.2.

## Requirements

### Validated

- ✓ Pullback strategy scanner with gate-based evaluation — existing
- ✓ Breakout strategy scanner with gate-based evaluation — existing
- ✓ Risk-based position sizing (stop/target engine) — existing
- ✓ Backtest infrastructure with trade simulator — existing
- ✓ Gate attribution analysis (which gates block what) — existing
- ✓ Post-mortem analysis for losing trades — existing
- ✓ Confidence scoring (regime-aware) — existing
- ✓ Web UI (Angular SPA + Express API) — existing
- ✓ SQLite signal/run/report persistence — existing
- ✓ Universe management (SP400/500/600) — existing
- ✓ Journal and live signal resolution — existing
- ✓ Industry group name on every signal (IND-01) — v1.0
- ✓ 20-day industry ETF momentum vs SPY on every signal (IND-02) — v1.0
- ✓ Industry ETF above/below 50-day MA flag on every signal (IND-03) — v1.0
- ✓ Within-run industry rank percentile on every signal (IND-04) — v1.0
- ✓ Industry momentum columns in schema v9 (IND-05) — v1.0
- ✓ Look-ahead-bias-free ETF momentum in backtest engine (IND-06) — v1.0
- ✓ Industry fields visible in CLI scan output and Angular signal table (IND-07) — v1.0
- ✓ Winner/loser median comparison in backtest reports — 6 pre-registered metrics (WLA-01, WLA-02) — v1.0
- ✓ Per-strategy W/L breakdown (pullback vs breakout not combined) (WLA-03) — v1.0
- ✓ Industry momentum as a W/L discriminant dimension (WLA-04) — v1.0
- ✓ Cell-size gate: suppress buckets < 50 trades (WLA-05) — v1.0
- ✓ Pre-registered feature list committed before viewing results (WLA-06) — v1.0
- ✓ Sector-filtered universe resolution via persisted ticker→GICS sector cache (SEAS-01) — v1.1 Phase 5
- ✓ Clear error + valid-sector listing on unknown sector name, no analysis run (SEAS-02) — v1.1 Phase 5
- ✓ Daily OHLCV reused from `data_store.get_history`, yfinance only on cache miss (SEAS-03) — v1.1 Phase 5
- ✓ Sub-2-year-history tickers skipped and logged with count (SEAS-04) — v1.1 Phase 5
- ✓ Missing/corrupt ticker cache skipped and logged, batch continues (SEAS-05) — v1.1 Phase 5
- ✓ Per-week mean/median/std daily log return in bps, n_obs, n_years for ISO weeks 1–52 (week 53 merged) (SEAS-06) — v1.1 Phase 6
- ✓ Each week's mean return expressed as delta vs. full-sample baseline (SEAS-07) — v1.1 Phase 6
- ✓ Year-block bootstrap 95% CI per week, reproducible via `--bootstrap-iters`/`--seed` (SEAS-08) — v1.1 Phase 6
- ✓ Significance flag set only when 95% CI excludes zero, no tuning (SEAS-09) — v1.1 Phase 6
- ✓ Synthetic test proves detection of an injected -30bps week-28 effect (SEAS-14) — v1.1 Phase 6
- ✓ Synthetic pure-noise run stays within ~0-3/52 false-positive band (SEAS-15) — v1.1 Phase 6
- ✓ CLI prints 52-row per-week table (week, mean/median/delta/CI/n_obs/n_years/significant) (SEAS-10) — v1.1 Phase 7
- ✓ CLI prints interpretive summary — baseline, significant weeks, top-5/bottom-5, multiple-comparison caveat (SEAS-11) — v1.1 Phase 7
- ✓ One-line survivorship-bias warning in output header (SEAS-12) — v1.1 Phase 7
- ✓ `--output` writes CSV while stdout output always happens regardless (SEAS-13) — v1.1 Phase 7

### Active

- [ ] Industry momentum gate promotion (IND-GATE-01) — promote to a hard gate only after backtest evidence demonstrates discriminating value
- [ ] Industry rank delta vs 4 weeks prior — momentum-of-momentum signal (IND-EXT-01)
- [ ] Statistical significance indicators on W/L metrics — p-values or confidence intervals (WLA-EXT-01)
- [ ] Win rate by quarter time-series — detect regime dependency in W/L patterns (WLA-EXT-02)

### Out of Scope

- Changing existing pullback/breakout gate thresholds or score formulas — stable, do not touch without new data
- Signal ranking / top-N selection — not the current focus
- Macro timing rules (FOMC avoidance, earnings season filters) — not prioritized
- IBD-style 197-group classification — proprietary, not available via yfinance
- Paid data feeds (Bloomberg, Refinitiv) — yfinance-only constraint; this is intentional

## Context

**Shipped:** v1.0 Signal Quality (2026-07-02), v1.1 Weekly Seasonality Analyzer (2026-07-12)

The v1.0 milestone delivered industry-group momentum context on every signal and a pre-registered winner/loser analysis in backtest reports. v1.1 added a standalone seasonality diagnostic on top of that foundation — the system now has instrumentation to investigate industry momentum, entry-time metrics, and calendar-week seasonality as potential winner/loser discriminants.

**Current state:**
- Scanner: Python scanner with 320 passing tests (up from 295 at v1.1 start — Phase 7 added CLI output/CSV-export tests plus a subprocess-based regression test for a Windows stream-encoding bug); schema v9 (12 tables, unchanged — the seasonality tool is diagnostic-only, no schema bump)
- Web: Express API (port 3000) + Angular SPA (port 4200); 71 + 37 passing tests (unaffected by v1.1 — the seasonality tool is CLI-only by design)
- Stack: Python/pandas/yfinance + SQLite + Node.js/Express + Angular 17
- Universe: SP400/500/600 (1,400 tickers); sample.txt for dev testing
- New this milestone: `seasonality_by_week.py` (CLI entry point), `scanner/sector_store.py` (ticker→GICS-sector Parquet cache), `scanner/seasonality.py` (log-return panel, year-block bootstrap CI, significance flagging, table/summary/CSV rendering)

**Next investigation:** Run a multi-year pullback backtest with the v1.0 codebase, then read the `wl_analysis` output to see whether industry momentum, RSI at entry, or RVOL actually discriminates winners from losers with sufficient sample size. This is the evidence base for gate promotion decisions in v2. Separately, `seasonality_by_week.py` is now available to check whether any given sector shows real (bootstrap-significant, not cherry-picked) calendar-week seasonality worth factoring into entry timing.

Key lessons from prior milestones:
- ADX gate removal degraded performance (reverted)
- Volume contraction gate removal also degraded performance (reverted)
- Empirical validation before any gate change is mandatory
- `bool(NaN)` evaluates to `True` in Python — guard pre-warm-up MACD with `pd.isna()` checks
- Signal key collision risk in dual-strategy backtests: use 3-tuple `(date, ticker, strategy)` for dict keys
- `np.percentile` (not `np.nanpercentile`) on bootstrap draws silently returns NaN + a false "not significant" for any week absent from even one resampled year — no exception, no warning. Caught by code review, not by the original test suite, since none of the fixtures constructed a week missing from a year. Any future per-week/per-group bootstrap in this codebase should default to `nanpercentile` plus an explicit insufficient-data flag, not bare `percentile`.
- Non-ASCII characters (e.g. `→`) in `print()` confirmation lines crash with `UnicodeEncodeError` on Windows, where the default console/stream encoding is `cp1252`, not UTF-8 — pytest's `capsys` never catches this because it captures via an in-memory buffer that bypasses real stream encoding. Found in `seasonality_by_week.py` and an identical pre-existing occurrence in `scan.py`; fixed by using ASCII-only output text. Any new CLI confirmation/status print in this codebase should stick to ASCII, and a genuine regression test for stream-encoding bugs needs `subprocess.run(..., env={"PYTHONIOENCODING": "cp1252"})`, not `capsys`.

## Constraints

- **Data source**: yfinance only — no paid data feeds; industry group data must be derivable from yfinance or the tickers themselves
- **Gate stability**: Do not change existing gate thresholds or score formulas without an explicit task backed by data
- **Test suite**: `pytest -q` must stay green after every Python change; `npm test` and `ng test` must stay green after web changes
- **Architecture**: New display fields flow through the same signal pipeline (scanner → DB → API → UI); no new tables without schema version bump

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Display-only for industry momentum | Follow the same evidence-first discipline that prevented two gate-removal mistakes | ✓ Validated — industry fields visible; gate promotion deferred to v2 pending backtest evidence |
| Industry group granularity over GICS sectors | Finer discrimination — sectors are too broad to be predictive at the individual stock level | ✓ Validated — industryKey slugs from yfinance map cleanly to SPDR ETF proxies |
| Winner vs loser analysis in backtest reports | ~50% stop rate with gate compliance means the answer is in the distribution, not a single threshold | ✓ Delivered — 6-metric pre-registered analysis with anti-cherry-picking guard |
| `WL_FEATURES` pre-registration before any backtest viewed | Anti-cherry-picking: feature list must not be influenced by observed results | ✓ Enforced — constant committed before results evaluated; pattern established for v2 |
| Schema v9 (not v7 as milestone originally named) | v7/v8 already consumed by prior epics; v9 is the correct next increment | ✓ Applied — schema_version = 9 in production DB |
| 3-tuple signal key in W/L analysis | Prevents collision in dual-strategy runs where same ticker appears in both strategies | ✓ Correct — found and fixed in code review (CR-02) |
| Year-block bootstrap (not naive daily resampling) for seasonality CIs | Naive resampling understates uncertainty given cross-sectional correlation within a sector — all tickers move together on any given day | ✓ Delivered — `bootstrap_week_ci` resamples whole years, baseline recomputed per iteration |
| GICS sector granularity only for seasonality (not sub-sector/industry) | Scoped explicitly to keep v1.1 diagnostic-only and small; industry-level would need the same ETF-proxy design work as v1.0's industry momentum feature | ✓ Applied — out of scope, documented in REQUIREMENTS.md |
| Seasonality tool is diagnostic-only — no scan/backtest/UI wiring, no schema bump | Evidence-first discipline (same as industry-momentum display-only rollout in v1.0) — promote to a gate only after backtest evidence | ✓ Applied — standalone CLI + CSV, zero changes to `store_db.py`/schema/web layer |
| Survivorship bias documented via warning, not corrected | Current-constituents-only universe; correcting would require delisted-ticker history not available via yfinance | ✓ Applied — one-line warning printed in every CLI run's header |



---

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-12 — v1.1 Weekly Seasonality Analyzer shipped*
