# Roadmap: TraderAssist — Signal Quality Milestone

## Overview

This milestone adds two capabilities to TraderAssist: industry-group momentum as a display field on every signal, and winner/loser characteristic analysis in backtest reports. The work proceeds in four phases: validate the industry classification and ETF data layer, compute and store momentum scores under schema v7 with full look-ahead bias prevention, surface the fields in CLI and web UI, then deliver the pre-registered W/L analysis in backtest reports.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Industry Classification + ETF Data Layer** - Validate yfinance industry strings and Parquet-cache ~10 industry ETF tickers as the foundation for all momentum computation
- [ ] **Phase 2: Industry Momentum Computation + Schema v7** - Compute 20-day momentum scores, above/below 50-day MA flag, and rank percentile on every signal without look-ahead bias; persist in dedicated schema v7 columns
- [ ] **Phase 3: Industry Display in CLI + Web UI** - Surface industry group name and momentum indicators in scan CLI output and the Angular signal table
- [ ] **Phase 4: Winner/Loser Characteristic Analysis** - Deliver pre-registered W/L breakdown in backtest reports with per-strategy tables, cell-size suppression, and sample-size abort

## Phase Details

### Phase 1: Industry Classification + ETF Data Layer
**Goal**: The pipeline knows each ticker's industry group and the industry ETF price series are Parquet-cached and ready for momentum computation.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: IND-01
**Success Criteria** (what must be TRUE):
  1. Fetching `.info['industry']` via yfinance for 10 representative tickers across sectors returns non-null string values that match INDUSTRY_ETF_MAP keys
  2. All ~10 industry ETF tickers added to `_MARKET_SYMBOLS` are downloaded and Parquet-cached without errors on `scan.py refresh`
  3. A ticker with no yfinance industry classification returns NULL (not empty string or 0.0) in `QualityInfo.industry`, verified by a unit test
  4. An industry with no direct ETF entry falls back to its sector-level ETF rather than raising an exception, verified by a unit test
**Plans**: 2 plans
- [ ] 01-01-PLAN.md — INDUSTRY_ETF_MAP + resolve_industry_etf() resolution chain + deduplicated _MARKET_SYMBOLS (wave 1)
- [ ] 01-02-PLAN.md — QualityInfo industry/industry_key fields + _make_quality_info() fetch (wave 2)

### Phase 2: Industry Momentum Computation + Schema v7
**Goal**: Every signal has industry group, 20-day momentum score, above/below 50-day MA flag, and rank percentile computed without look-ahead bias and stored in dedicated DB columns under schema v7.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: IND-02, IND-03, IND-04, IND-05, IND-06
**Success Criteria** (what must be TRUE):
  1. Running `scan.py scan` produces signals with non-null `industry_group` (TEXT) and `industry_momentum` (REAL) columns in scanner.db; `schema_version` reads 7
  2. Each signal row carries a 20-day ETF momentum score vs SPY (IND-02), an above/below 50-day MA boolean (IND-03), and an industry rank percentile among all industries in the scan run (IND-04)
  3. A backtest spot-check on a specific historical date confirms the ETF close price used equals the actual historical close on that date — no future prices consumed
  4. A ticker with no matched industry ETF stores NULL in `industry_momentum` (not 0.0); the NULL survives DB round-trip without coercion to any numeric value
**Plans**: TBD

### Phase 3: Industry Display in CLI + Web UI
**Goal**: Industry group name and momentum indicators are visible to the user in scan CLI output and the Angular signal table.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: IND-07
**Success Criteria** (what must be TRUE):
  1. Running `scan.py scan --strategy pullback --ticker AAPL` prints the industry group name and 20-day momentum score in CLI output alongside other signal fields
  2. The Angular signal table renders an industry group column and a momentum indicator column for every loaded signal
  3. A signal where `industry_momentum` is NULL displays a dash (—) in the web UI, not 0.0 or an empty cell
  4. The TypeScript `Signal` interface includes `industry_group` and `industry_momentum` fields; `ng build` and `ng test` pass without errors
**Plans**: TBD
**UI hint**: yes

### Phase 4: Winner/Loser Characteristic Analysis
**Goal**: Backtest reports include a rigorous pre-registered breakdown of what entry-time metrics discriminate winners from losers, with explicit guards against spurious findings from small samples or undisclosed feature selection.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: WLA-01, WLA-02, WLA-03, WLA-04, WLA-05, WLA-06
**Success Criteria** (what must be TRUE):
  1. Running a backtest with sufficient history produces a W/L analysis section showing median values for at least 6 entry-time metrics — RSI at entry, RVOL, pullback depth %, ATR multiple, industry momentum score, pct to 52-week high — for winners vs losers, separately for pullback and breakout strategies
  2. The analyzed feature list is defined as a fixed constant in `report.py` source code before any backtest results are viewed; it is readable in code independently of any run output
  3. Any metric bucket with fewer than 50 trades displays an explicit suppression warning instead of median values
  4. When total qualified trades fall below 200, the analysis outputs an explicit warning and produces no comparison table
  5. Industry momentum score appears as one column in the winner vs loser comparison table
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Industry Classification + ETF Data Layer | 0/0 | Not started | - |
| 2. Industry Momentum Computation + Schema v7 | 0/0 | Not started | - |
| 3. Industry Display in CLI + Web UI | 0/0 | Not started | - |
| 4. Winner/Loser Characteristic Analysis | 0/0 | Not started | - |
