# Codebase Structure

**Analysis Date:** 2026-07-02

## Directory Layout

```
TraderAssist/
├── scan.py                    # Unified CLI entry point — all subcommands
├── scanner/                   # Core Python engine package
│   ├── __init__.py
│   ├── core.py                # GateLog, EvalContext, QualityInfo, indicators, context factory
│   ├── data_store.py          # Parquet OHLCV cache; only yfinance price importer
│   ├── earnings_store.py      # Parquet earnings-date cache
│   ├── targets.py             # Stop/target/sizing engine
│   ├── regime.py              # Market regime, ATH zone, confidence scoring
│   ├── backtest.py            # Historical signal generation loop
│   ├── simulate.py            # Signal → Trade simulation; Signal dataclass
│   ├── report.py              # Metrics computation, report rendering, winner/loser analysis
│   ├── store_db.py            # ALL SQL; data/scanner.db schema and queries
│   ├── journal.py             # Live signal write, open-signal resolution, backtest comparison
│   ├── universe.py            # Universe build, audit, load
│   ├── postmortem.py          # Post-mortem analysis helpers
│   └── strategies/
│       ├── pullback.py        # evaluate() → PullbackResult
│       └── breakout.py        # evaluate() → BreakoutResult
├── tests/                     # pytest test suite
│   ├── conftest.py            # Shared fixtures (monkeypatches, mock market data)
│   ├── golden/                # Golden-master reference files for snapshot tests
│   ├── test_backtest.py
│   ├── test_core.py
│   ├── test_data_store.py
│   ├── test_earnings_store.py
│   ├── test_fixtures.py
│   ├── test_golden_master.py
│   ├── test_journal.py
│   ├── test_postmortem.py
│   ├── test_regime.py
│   ├── test_report.py
│   ├── test_scan_display.py
│   ├── test_simulate.py
│   ├── test_store_db.py
│   ├── test_strategies.py
│   ├── test_targets.py
│   └── test_universe.py
├── web/
│   ├── api/                   # Express.js read-only API (port 3000)
│   │   ├── server.js          # HTTP server bootstrap
│   │   ├── app.js             # Express app, route registration
│   │   ├── db/                # DB connection helper (better-sqlite3)
│   │   ├── routes/            # One file per resource
│   │   │   ├── health.js
│   │   │   ├── signals.js
│   │   │   ├── runs.js
│   │   │   ├── journal.js
│   │   │   ├── stats.js
│   │   │   ├── jobs.js
│   │   │   └── ohlcv.js
│   │   └── tests/             # API Jest tests
│   └── ui/                    # Angular SPA (port 4200)
│       └── src/app/
│           ├── app.module.ts
│           ├── app-routing.module.ts
│           ├── pages/
│           │   ├── candidates/    # Live scan signal list
│           │   ├── backtests/     # Backtest run list and report
│           │   ├── calibration/   # Winner/loser characteristic analysis
│           │   ├── dashboard/     # Summary overview
│           │   ├── diagnosis/     # Single-ticker gate-level diagnose
│           │   └── journal/       # Live signal tracking and resolution
│           ├── services/
│           │   └── api.service.ts # HTTP client for Express API
│           └── shared/            # Shared components and utilities
├── data/
│   ├── scanner.db             # SQLite database (schema v9)
│   ├── ohlcv/                 # {TICKER}.parquet — daily OHLCV cache
│   └── earnings/              # {TICKER}_earnings.parquet
├── universes/                 # Universe text files (one ticker per line)
│   ├── sp400.txt
│   ├── sp500.txt
│   ├── sp600.txt
│   └── sample.txt
├── runs/                      # Backtest output directories
│   └── {run_name}/            # metrics.json, signals CSV, report artifacts
├── .planning/                 # GSD planning artifacts
│   ├── config.json
│   ├── codebase/              # Codebase map documents (this directory)
│   ├── phases/                # Active phase plans
│   ├── milestones/            # Archived completed milestones
│   └── research/              # Research notes and cache
└── legacy/                    # Retired scripts (not imported anywhere)
    ├── swing_scanner.py
    ├── pullback_filter.py
    └── breakout_filter.py
```

## Directory Purposes

**`scanner/`:**
- Purpose: The entire Python scanning engine as an importable package
- Contains: Data layer, context assembly, strategy evaluation, risk, simulation, reporting, DB layer
- Key files: `core.py` (shared abstractions), `store_db.py` (all SQL), `strategies/` (evaluate functions)

**`scanner/strategies/`:**
- Purpose: One file per trading strategy; each exports a pure `evaluate()` function
- Contains: `pullback.py`, `breakout.py`; each strategy's result dataclass defined here
- Key files: `pullback.py` (PullbackResult), `breakout.py` (BreakoutResult)

**`tests/`:**
- Purpose: pytest test suite — one test file per scanner module
- Contains: Unit and integration tests; golden-master snapshot tests; offline only (all yfinance calls monkeypatched)
- Key files: `conftest.py` (shared fixtures), `golden/` (snapshot references)

**`web/api/`:**
- Purpose: Express.js HTTP API bridging `scanner.db` to the Angular SPA; read-only
- Contains: Route handlers per DB table/resource; better-sqlite3 connection wrapper
- Key files: `app.js` (route wiring), `routes/signals.js` (primary endpoint)

**`web/ui/src/app/`:**
- Purpose: Angular SPA for browsing signals, backtests, journal, and diagnoses
- Contains: Feature pages, shared components, single API service
- Key files: `services/api.service.ts` (all HTTP calls), `pages/candidates/` (main signal view)

**`data/`:**
- Purpose: Runtime data storage; never committed (except `scanner.db` schema bootstraps on first run)
- Contains: SQLite database, Parquet OHLCV cache, Parquet earnings cache
- Generated: Yes — populated by `scan.py refresh` and scan runs

**`universes/`:**
- Purpose: Plain-text ticker lists used as scan inputs
- Contains: S&P 400/500/600 lists and a sample list for demos
- Format: One ticker per line; lines starting with `#` are comments

**`runs/`:**
- Purpose: Output directory for backtest runs; each run gets a named subdirectory
- Contains: Signal exports, metric JSON, report artifacts
- Generated: Yes — created by `python scan.py backtest --out runs/{name}/`

**`legacy/`:**
- Purpose: Retired original scanner scripts; kept for historical reference only
- Contains: `swing_scanner.py`, `pullback_filter.py`, `breakout_filter.py`
- Note: Not imported by any active code; safe to ignore

## Key File Locations

**Entry Points:**
- `scan.py`: All CLI subcommands — scan, refresh, backtest, journal, universe, worker

**Core Abstractions:**
- `scanner/core.py`: GateLog, EvalContext, QualityInfo, SECTOR_ETF_MAP, INDUSTRY_ETF_MAP, all shared indicators, `make_context()`, `make_contexts()`, `run_scan()`, `last_closed_session()`

**Strategy Evaluation:**
- `scanner/strategies/pullback.py`: Pullback gate logic and PullbackResult dataclass
- `scanner/strategies/breakout.py`: Breakout gate logic and BreakoutResult dataclass

**Data Access:**
- `scanner/data_store.py`: `get_history()`, `get_weekly()`, `get_market_data()` — yfinance + Parquet
- `scanner/earnings_store.py`: `days_to_earnings()` — earnings date Parquet cache

**Persistence:**
- `scanner/store_db.py`: Schema DDL, all INSERT/SELECT/UPDATE, `open_db()`, migration; `_SCHEMA_VERSION = 9`
- `data/scanner.db`: SQLite database (tables: signals, runs, backtest_reports, jobs, bars, schema_version)

**Risk & Regime:**
- `scanner/targets.py`: `attach_risk()`, stop/target formulas, `SizeInfo`, `compute_size()`
- `scanner/regime.py`: `market_regime()`, `ath_zone()`, `compute_confidence()`

**Simulation & Reporting:**
- `scanner/simulate.py`: `Signal` dataclass, `simulate_trades()` → list of Trade
- `scanner/report.py`: `compute_metrics()`, `render_report()`, gate attribution, winner/loser analysis
- `scanner/journal.py`: `write_live_signals()`, `resolve_open_signals()`, `compare_with_backtest()`

**API:**
- `web/api/app.js`: Express route registration; mounts all route files under `/api`
- `web/api/routes/signals.js`: `/api/signals` — primary data endpoint
- `web/api/routes/jobs.js`: `/api/jobs` — on-demand diagnose job queue

**UI:**
- `web/ui/src/app/services/api.service.ts`: Single Angular service for all HTTP calls
- `web/ui/src/app/pages/candidates/`: Primary signal browsing page

**Testing:**
- `tests/conftest.py`: Shared pytest fixtures; monkeypatches yfinance calls
- `tests/golden/`: Golden-master files for snapshot regression tests

## Naming Conventions

**Python Files:**
- `snake_case.py` for all scanner modules
- One module per concern: `data_store.py`, `earnings_store.py`, `store_db.py`, `targets.py`
- Strategy files named after the strategy: `pullback.py`, `breakout.py`
- Test files named `test_{module}.py` matching the module they test

**Python Classes:**
- `PascalCase` for dataclasses and classes: `GateLog`, `EvalContext`, `QualityInfo`, `PullbackResult`, `BreakoutResult`, `Signal`, `Trade`, `SizeInfo`

**Python Constants:**
- `UPPER_SNAKE_CASE` for all thresholds and maps: `RSI_PULLBACK_RANGE`, `SECTOR_ETF_MAP`, `INDUSTRY_ETF_MAP`, `EARNINGS_BUFFER_DAYS`

**Python Functions:**
- `snake_case` for public functions: `run_scan()`, `make_context()`, `attach_risk()`
- `_leading_underscore` for private/internal helpers: `_make_quality_info()`, `_bullish_reversal_candle()`, `_sector_strength()`

**JavaScript/TypeScript Files:**
- Route files: `{resource}.js` (e.g., `signals.js`, `runs.js`)
- Angular: `{feature}.component.ts`, `{feature}.service.ts`, `{feature}.module.ts`

**Database:**
- Table names: `snake_case` plural (e.g., `signals`, `runs`, `backtest_reports`)
- Column names: `snake_case` (e.g., `gate_detail_json`, `run_id`, `failed_gates`)

## Where to Add New Code

**New Strategy:**
- Implementation: `scanner/strategies/{strategy_name}.py` — export `evaluate(ticker, df, ctx, verbose) -> {Strategy}Result`
- Register in: `scan.py _strategy_fn_for()` and `cmd_scan()` strategy routing
- Tests: `tests/test_strategies.py` or new `tests/test_{strategy_name}.py`

**New Gate or Indicator:**
- Shared indicator (used by multiple strategies): Add helper function to `scanner/core.py` with `_` prefix
- Strategy-specific gate: Add inside `scanner/strategies/{strategy}.py evaluate()`
- New constant/threshold: Add to `scanner/core.py` constants block; import in strategy file

**New DB Column:**
- Bump `_SCHEMA_VERSION` in `scanner/store_db.py`
- Add column to DDL in `_DDL` string
- Add migration branch in the schema migration function
- Update insert/select functions in `store_db.py`

**New API Endpoint:**
- Implementation: `web/api/routes/{resource}.js`
- Register: `web/api/app.js` — `app.use('/api', {resource}Router)`

**New UI Page:**
- Directory: `web/ui/src/app/pages/{page-name}/`
- Register route: `web/ui/src/app/app-routing.module.ts`
- HTTP calls: via `web/ui/src/app/services/api.service.ts`

**New Universe File:**
- Location: `universes/{name}.txt`
- Format: One ticker per line; `#` for comments; pass with `--file universes/{name}.txt`

**New Backtest Run:**
- Command: `python scan.py backtest --strategy {strategy} --file universes/{universe}.txt --start {date} --end {date} --out runs/{name}/`
- Output lands in: `runs/{name}/`

## Special Directories

**`data/`:**
- Purpose: Runtime data — SQLite DB and Parquet caches
- Generated: Yes — populated at runtime; not committed to git (except `scanner.db` is tracked but evolves)
- Note: `data/ohlcv/` and `data/earnings/` are gitignored; `data/scanner.db` is tracked

**`runs/`:**
- Purpose: Backtest output artifacts
- Generated: Yes — created by `scan.py backtest --out`
- Committed: Partially — named runs may be committed for reference; `runs/latest/` is a symlink/alias to most recent run

**`legacy/`:**
- Purpose: Retired original scanner files; historical reference only
- Generated: No
- Committed: Yes — preserved for reference but never imported

**`.planning/`:**
- Purpose: GSD workflow artifacts — phase plans, milestones, codebase maps
- Generated: By GSD commands
- Committed: Yes

---

*Structure analysis: 2026-07-02*
