<!-- refreshed: 2026-07-02 -->
# Architecture

**Analysis Date:** 2026-07-02

## System Overview

```text
┌──────────────────────────────────────────────────────────────┐
│                    CLI Entry Point                           │
│                    `scan.py`                                 │
└────────┬──────────────┬────────────────┬────────────────────┘
         │              │                │
         ▼              ▼                ▼
┌──────────────┐ ┌────────────┐ ┌──────────────────────────┐
│  scan cmd    │ │backtest cmd│ │  journal/universe/worker  │
│  (live scan) │ │(historical)│ │       cmds               │
└──────┬───────┘ └─────┬──────┘ └──────────┬───────────────┘
       │               │                    │
       ▼               ▼                    │
┌──────────────────────────────────────┐    │
│         scanner/ package             │    │
│  ┌──────────────────────────────┐    │    │
│  │ core.py                      │    │    │
│  │  GateLog, EvalContext,       │    │    │
│  │  QualityInfo, make_context() │    │    │
│  └────────┬─────────────────────┘    │    │
│           │                          │    │
│  ┌────────▼──────────────────────┐   │    │
│  │ strategies/                   │   │    │
│  │  pullback.py → PullbackResult │   │    │
│  │  breakout.py → BreakoutResult │   │    │
│  └────────┬──────────────────────┘   │    │
│           │                          │    │
│  ┌────────▼──────────────────────┐   │    │
│  │ targets.py  regime.py         │   │    │
│  │  attach_risk, confidence      │   │    │
│  └────────┬──────────────────────┘   │    │
│           │                          │    │
│  ┌────────▼──────────────────────┐   │    │
│  │ backtest.py / simulate.py     │◄──┘    │
│  └────────┬──────────────────────┘        │
│           │                               │
│  ┌────────▼──────────────────────┐        │
│  │ store_db.py                   │◄───────┘
│  │  ALL SQL — data/scanner.db    │
│  └────────┬──────────────────────┘
└───────────┼──────────────────────────┘
            │
            ▼
┌────────────────────────────────────────┐
│       data/scanner.db (SQLite)         │
│  signals, runs, backtest_reports,      │
│  jobs, bars, schema_version            │
└────────────────┬───────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────┐
│       web/api/ (Express, port 3000)    │
│  server.js → app.js → routes/*.js      │
│  Read-only via better-sqlite3          │
└────────────────┬───────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────┐
│       web/ui/ (Angular, port 4200)     │
│  pages/, services/api.service.ts       │
└────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI dispatcher | Parse subcommands; route to cmd_* handlers | `scan.py` |
| GateLog | Non-short-circuit gate accumulator; tracks pass/fail/skip/bonus per gate | `scanner/core.py` |
| EvalContext | Frozen dataclass carrying all inputs for one ticker evaluation (OHLCV, quality, market data, date) | `scanner/core.py` |
| QualityInfo | Frozen dataclass for fundamental data (market cap, debt/equity, sector, industry) | `scanner/core.py` |
| make_context / make_contexts | Context factory; fetches history, market data, earnings, quality from yfinance | `scanner/core.py` |
| pullback.evaluate() | Gate-based pullback setup detection; returns PullbackResult | `scanner/strategies/pullback.py` |
| breakout.evaluate() | Gate-based breakout setup detection; returns BreakoutResult | `scanner/strategies/breakout.py` |
| targets.attach_risk | Attach stop, target, ATR, position sizing to a signal | `scanner/targets.py` |
| regime.py | Market regime classification; confidence scoring | `scanner/regime.py` |
| data_store.py | Parquet OHLCV cache; only module that calls yfinance for price history | `scanner/data_store.py` |
| earnings_store.py | Parquet earnings-date cache | `scanner/earnings_store.py` |
| backtest.py | Historical signal generation loop (generate_signals) | `scanner/backtest.py` |
| simulate.py | Trade simulation from signals (simulate_trades); Signal dataclass | `scanner/simulate.py` |
| report.py | Metrics computation and report rendering; winner/loser analysis | `scanner/report.py` |
| journal.py | Live signal writing; open-signal resolution; backtest comparison | `scanner/journal.py` |
| universe.py | Universe build, audit, load | `scanner/universe.py` |
| store_db.py | ALL SQL; SQLite schema DDL; every query and write | `scanner/store_db.py` |
| postmortem.py | Post-mortem analysis helpers | `scanner/postmortem.py` |
| Express API | Read-only HTTP layer over scanner.db; routes per resource | `web/api/app.js`, `web/api/routes/*.js` |
| Angular SPA | Signal display, charts, diagnosis, journal, backtests UI | `web/ui/src/app/` |

## Pattern Overview

**Overall:** Layered pipeline with gate-based evaluation — data layer → context assembly → strategy evaluation → risk attachment → DB persistence → read-only API → SPA display.

**Key Characteristics:**
- Strategies are pure functions (no I/O, no wall-clock calls) that receive an `EvalContext` and return a typed result dataclass
- All SQL is centralised in `store_db.py`; no SQL anywhere else
- yfinance calls for price history are confined to `data_store.py` and `earnings_store.py`; `core.py` calls yfinance only for `.info` and `.calendar` (quality/earnings)
- `ctx.as_of` is the single source of truth for "today" inside evaluation logic — `datetime.now()` is banned inside strategies
- The web layer is strictly read-only; it never writes to `scanner.db`

## Layers

**Data Ingestion:**
- Purpose: Fetch and cache raw OHLCV data, earnings dates, and ETF market context from yfinance
- Location: `scanner/data_store.py`, `scanner/earnings_store.py`
- Contains: `get_history()`, `get_weekly()`, `get_market_data()`, `resample_weekly()`, Parquet read/write
- Depends on: yfinance
- Used by: `scanner/core.py` (via `make_context`)

**Context Assembly:**
- Purpose: Build a fully self-contained `EvalContext` per ticker for evaluation
- Location: `scanner/core.py` — `make_context()`, `make_contexts()`
- Contains: Quality info fetching, earnings date resolution, market data loading
- Depends on: `data_store.py`, `earnings_store.py`, yfinance `.info`/`.calendar`
- Used by: `scan.py` (live scan), `scanner/backtest.py` (historical)

**Strategy Evaluation:**
- Purpose: Apply gate checks to an `EvalContext` and return a typed result
- Location: `scanner/strategies/pullback.py`, `scanner/strategies/breakout.py`
- Contains: `evaluate(ticker, df, ctx, verbose)` returning `PullbackResult` / `BreakoutResult`
- Depends on: `scanner/core.py` (shared indicators, constants, GateLog, EvalContext)
- Used by: `scan.py` `cmd_scan`, `scanner/backtest.py` `generate_signals()`

**Risk Attachment:**
- Purpose: Compute stops, targets, ATR, position sizing
- Location: `scanner/targets.py`, `scanner/regime.py`
- Contains: `attach_risk()`, `market_regime()`, `compute_confidence()`, `ath_zone()`
- Depends on: `scanner/core.py` constants
- Used by: `scan.py` after strategy evaluation; `scanner/backtest.py`

**Persistence:**
- Purpose: Write and read all data in `data/scanner.db`
- Location: `scanner/store_db.py`
- Contains: Schema DDL (v9), every INSERT/SELECT/UPDATE, `open_db()`, migration logic
- Depends on: `sqlite3` stdlib only
- Used by: `scan.py` all subcommands, `scanner/journal.py`, `scanner/report.py`, `scanner/backtest.py`

**Simulation & Reporting:**
- Purpose: Convert historical signals to trade outcomes; compute metrics
- Location: `scanner/simulate.py`, `scanner/report.py`, `scanner/journal.py`
- Contains: `Signal` dataclass, `simulate_trades()`, `compute_metrics()`, `render_report()`, `write_live_signals()`, `resolve_open_signals()`
- Depends on: `scanner/store_db.py`
- Used by: `scan.py backtest`, `scan.py journal`

**API Layer:**
- Purpose: Serve `scanner.db` data as JSON over HTTP; read-only
- Location: `web/api/server.js`, `web/api/app.js`, `web/api/routes/*.js`, `web/api/db/`
- Contains: Express routes for signals, runs, journal, stats, jobs, ohlcv, health
- Depends on: `better-sqlite3`, `scanner.db` (read-only)
- Used by: Angular SPA

**UI Layer:**
- Purpose: Visualise signals, charts, backtests, journal, diagnosis
- Location: `web/ui/src/app/`
- Contains: Angular pages (candidates, backtests, calibration, dashboard, diagnosis, journal), `services/api.service.ts`
- Depends on: Express API at `http://localhost:3000`
- Used by: End user (browser)

## Data Flow

### Live Scan Path

1. `scan.py cmd_scan` resolves universe tickers (`scan.py:76`)
2. `core.make_contexts()` builds `EvalContext` per ticker — loads Parquet cache, fetches yfinance `.info` (`scanner/core.py:564`)
3. `strategies/pullback.evaluate()` or `breakout.evaluate()` runs gate checks, returns typed result (`scanner/strategies/pullback.py`, `scanner/strategies/breakout.py`)
4. `targets.attach_risk()` computes stop/target/ATR/sizing (`scanner/targets.py`)
5. `regime.compute_confidence()` attaches confidence label (`scanner/regime.py`)
6. `store_db.py` inserts signal row into `signals` table (`scanner/store_db.py`)
7. Express API serves signal via `/api/signals` (`web/api/routes/signals.js`)
8. Angular `CandidatesPage` renders result (`web/ui/src/app/pages/candidates/`)

### Backtest Path

1. `scan.py cmd_backtest` iterates date range over tickers
2. `backtest.generate_signals()` builds historical `EvalContext` per (ticker, date) using `PrecomputedBars` cache (`scanner/backtest.py`)
3. Strategy `evaluate()` called per date (same function as live scan)
4. `simulate.simulate_trades()` converts signals to `Trade` outcomes (`scanner/simulate.py`)
5. `report.compute_metrics()` aggregates win rate, R-multiple, etc. (`scanner/report.py`)
6. Results stored in `runs` + `backtest_reports` tables via `store_db.py`

### On-Demand Diagnose Path

1. UI posts job to `/api/jobs` → Express inserts row in `jobs` table
2. `scan.py worker --once` polls `jobs` table, executes diagnose for ticker
3. Result written back to `jobs.result_ref`
4. UI polls job status and displays gate detail

**State Management:**
- All persistent state lives in `data/scanner.db` (SQLite)
- In-memory Parquet cache for OHLCV data managed by `data_store.py`
- No shared mutable state between scan runs; `EvalContext` is frozen

## Key Abstractions

**GateLog:**
- Purpose: Accumulate gate pass/fail/skip/bonus results without short-circuiting; produce ordered `gate_detail_json` for storage
- Examples: `scanner/core.py:125`
- Pattern: Every gate call returns `bool`; strategy continues evaluating all gates regardless of failures; `qualified` property is True only if zero failures

**EvalContext:**
- Purpose: Immutable bundle of all data needed to evaluate one ticker at one point in time
- Examples: `scanner/core.py:204`
- Pattern: Frozen dataclass — `as_of`, `market_data`, `weekly`, `quality`, `days_to_earnings`

**Strategy evaluate():**
- Purpose: Pure function contract — takes `(ticker, df, ctx, verbose)`, returns typed result dataclass with `gate_log` and `qualified` fields
- Examples: `scanner/strategies/pullback.py`, `scanner/strategies/breakout.py`
- Pattern: No I/O, no wall-clock, no `datetime.now()` inside; all data comes from `ctx`

**store_db.py as SQL boundary:**
- Purpose: Single module owns all SQL; swappable to Postgres by replacing one file
- Examples: `scanner/store_db.py`
- Pattern: No raw SQL in any other module; connection opened via `open_db()`

## Entry Points

**Live Scan:**
- Location: `scan.py` → `cmd_scan()`
- Triggers: `python scan.py scan --strategy pullback --file universes/sp500.txt`
- Responsibilities: Universe load, context build, strategy evaluation, risk attachment, DB write, console output

**Backtest:**
- Location: `scan.py` → `cmd_backtest()` → `scanner/backtest.py generate_signals()`
- Triggers: `python scan.py backtest --strategy pullback --file universes/sp500.txt --start ... --end ...`
- Responsibilities: Historical signal generation, trade simulation, metrics, report write

**Worker (On-demand diagnose):**
- Location: `scan.py` → `cmd_worker()` → polls `jobs` table
- Triggers: `python scan.py worker --once`
- Responsibilities: Dequeue job, run single-ticker diagnose, write result back

**Express API:**
- Location: `web/api/server.js` → `app.js`
- Triggers: HTTP requests from Angular SPA
- Responsibilities: Read-only queries against `scanner.db`; JSON responses

## Architectural Constraints

- **yfinance isolation:** Only `scanner/data_store.py` and `scanner/earnings_store.py` import yfinance for price/earnings history. `scanner/core.py` calls yfinance only for `Ticker.info` and `Ticker.calendar`. No other module may import yfinance for prices.
- **No datetime.now() in evaluation:** Strategy modules and `EvalContext` consumers must use `ctx.as_of` for "today". `datetime.now()` is only allowed at the CLI entry point (`scan.py`) and in `core.last_closed_session()`.
- **SQL boundary:** All SQL lives in `scanner/store_db.py`. No raw SQL in any other module.
- **Web layer read-only:** `web/api/` never writes to `scanner.db`. All writes go through the Python engine via `scan.py`.
- **Schema versioning:** Every schema change requires a version bump in `store_db._SCHEMA_VERSION` (current: 9) and a migration branch.
- **Windows reserved names:** Ticker names matching Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) are filtered at universe load and in all `data_store` entry points.
- **Gate thresholds:** Constants in `scanner/core.py` are frozen decisions. Do not change without explicit data-backed task.

## Anti-Patterns

### Calling yfinance outside data_store / earnings_store / core quality fetch

**What happens:** A strategy or utility module imports yfinance and calls `yf.download()` directly.
**Why it's wrong:** Breaks the caching layer; introduces network I/O into pure evaluation functions; makes backtesting non-deterministic.
**Do this instead:** Call `get_history()` or `get_market_data()` from `scanner/data_store.py`, or access pre-fetched data from `ctx.market_data`.

### Using datetime.now() inside evaluation logic

**What happens:** A strategy reads the wall clock to determine "today".
**Why it's wrong:** Makes the strategy non-replayable for backtesting; `as_of` in historical mode would be ignored.
**Do this instead:** Use `ctx.as_of` which is set correctly for both live and historical runs.

### Writing SQL outside store_db.py

**What happens:** A route handler or utility builds a raw SQL string and calls `sqlite3.connect()` directly.
**Why it's wrong:** Undermines the "swappable to Postgres" guarantee; scatters schema knowledge across files.
**Do this instead:** Add a function to `scanner/store_db.py` and call it.

## Error Handling

**Strategy:** Strategies return a result dataclass with `qualified=False` and populated `failed_gates` when gates fail — they do not raise exceptions for gate failures. Network/data errors in context building return `None` from `make_context()`, and the ticker is skipped in `run_scan`.

**Patterns:**
- `make_context()` returns `None` on data unavailability; callers skip the ticker
- yfinance `.info` fetch retries 3× with exponential backoff before giving a conservative default (`QualityInfo` with `profitable=False`)
- Earnings date unknown → `days_to_earnings=None` → strategy gate uses SKIP (not fail)
- Weekly data unavailable → `ctx.weekly=None` → strategy gate uses SKIP

## Cross-Cutting Concerns

**Logging:** `logging` stdlib; module-level loggers named `scanner.<module>` (e.g., `scanner.quality`, `scanner.backtest`). Console output for CLI uses `print()` directly.
**Validation:** Gate-based — `GateLog` accumulates failures rather than raising; invalid data is handled with SKIP semantics.
**Authentication:** None — single-user local tool; Express API has no auth middleware.

---

*Architecture analysis: 2026-07-02*
