# Architecture Research

**Domain:** Industry momentum integration — existing Python swing trading scanner
**Researched:** 2026-06-30
**Confidence:** HIGH — based on direct codebase reading, not inference

---

## Existing System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  CLI (scan.py)                                                       │
│  scan | backtest | journal | refresh | universe | worker             │
├───────────────────────────────┬─────────────────────────────────────┤
│  Scanner Engine               │  Backtest Engine                    │
│  core.run_scan()              │  backtest.generate_signals()        │
│  ├─ make_contexts()           │  ├─ _precompute_bars()              │
│  ├─ strategy.evaluate()       │  ├─ _make_context_from_frames()     │
│  ├─ targets.attach_risk()     │  ├─ strategy.evaluate()             │
│  └─ compute_confidence()      │  ├─ targets.attach_risk()           │
│                               │  ├─ compute_confidence()            │
│                               │  └─ simulate_trades()               │
├───────────────────────────────┴─────────────────────────────────────┤
│  Data Layer                                                          │
│  data_store.py          earnings_store.py     store_db.py           │
│  Parquet (data/ohlcv/)  Parquet (data/earn.)  SQLite (scanner.db)  │
│  get_history()          get_earnings_dates()  insert_signal()       │
│  get_market_data()                            insert_backtest_rpt() │
│  ← ONLY yfinance price  ← ONLY yfinance earn  ← ALL SQL             │
│    calls live here        calls live here                            │
├─────────────────────────────────────────────────────────────────────┤
│  Web Layer                                                           │
│  Express API (port 3000)          Angular SPA (port 4200)           │
│  routes/signals.js                services/api.service.ts           │
│  routes/runs.js                   pages/candidates                  │
│  routes/jobs.js                   pages/backtests                   │
│  db.js (better-sqlite3)           pages/journal                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

| Component | Responsibility | Key Constraint |
|-----------|----------------|----------------|
| `data_store.py` | OHLCV Parquet cache + market ETF data. Only module importing yfinance for prices. | `_MARKET_SYMBOLS` list drives what ETFs are cached |
| `core.py` | `EvalContext`, `QualityInfo`, indicators, `run_scan()`, `make_contexts()`, `SECTOR_ETF_MAP` | `_make_quality_info()` fetches `sector` from `yf.Ticker().info` |
| `backtest.py` | Historical signal loop; pre-computes indicators once, then `.asof()` per day | No disk I/O inside the day×ticker inner loop |
| `store_db.py` | ALL SQL; schema migrations; single source of truth for DB structure | Schema version bumped per structural change |
| `report.py` | Metrics, attribution, forensics, `render_report()` → `(md, json_out)` | `json_out` is stored in `backtest_reports.metrics_json` |
| `simulate.py` | `Signal` and `Trade` dataclasses; `simulate_trades()` | `Signal` carries entry-time data; `Trade` carries outcome |
| Express API | Read-only DB access via `better-sqlite3`; routes decompose `metrics_json` blob | `runs/:run_id` manually unpacks report JSON fields |
| Angular UI | `Signal` and `Run` TypeScript interfaces mirror API shape exactly | New API fields need new TS interface fields |

---

## How the Two New Features Integrate

### Feature 1: Industry Momentum as Display Field

**Current state** — the infrastructure is partially in place:
- `SECTOR_ETF_MAP` in `core.py` already maps 11 sector names → ETF symbols
- `_sector_strength()` in `core.py` already computes `sector_above_50ma` and `sector_outperforming` from `market_data`
- `quality.sector` (from `yf.Ticker().info['sector']`) already flows through `EvalContext`
- All sector ETFs (XLK, XLF, etc.) are already in `_MARKET_SYMBOLS` and cached by `get_market_data()`
- `ath_zone` shows the exact integration pattern: computed per-signal in `run_scan()` / `generate_signals()`, stored as a column in `signals`, passed through API, displayed in UI

**What is missing** — four changes across four layers:

1. **Classification**: `QualityInfo.industry: Optional[str]` — fetch from `yf.Ticker().info['industry']` inside `_make_quality_info()`, same call as `sector`. No new network round-trip.

2. **ETF mapping**: `INDUSTRY_ETF_MAP` dict in `core.py`, similar to `SECTOR_ETF_MAP`. Maps ~20 yfinance industry names to their best-matching sub-sector ETF (e.g., `"Semiconductors" → "XSD"`, `"Banks—Regional" → "KRE"`, `"Biotechnology" → "XBI"`). Where no industry-specific ETF exists, fall back to the sector ETF via `SECTOR_ETF_MAP`. Coverage is best-effort; NULL is valid for unmapped industries.

3. **ETF data**: New industry ETF symbols (XSD, KRE, KBE, XOP, XBI, XRT, ITA, XHB, IHI, KIE, etc.) added to `_MARKET_SYMBOLS` in `data_store.py`. The `get_market_data()` function picks them up automatically — no other change to the data layer.

4. **Computation**: A `_industry_momentum()` helper in `core.py` that takes `(industry, market_data, spy_df)` and returns `{"industry_etf": str|None, "industry_rs": float|None, "industry_above_50ma": bool}`. Follows the same pattern as `_sector_strength()`. Computed in the same block as `ath_zone` and confidence inside `run_scan()` and `generate_signals()`.

**Signal pipeline wiring** — both scan loops need the same two additions:
- Read `quality.industry` (already in context after QualityInfo change)
- Call `_industry_momentum(quality.industry, market_data)` → store `industry_momentum REAL` (the RS ratio) and `industry TEXT` on the output row

**DB schema (v9)**:
```sql
ALTER TABLE signals ADD COLUMN industry TEXT;
ALTER TABLE signals ADD COLUMN industry_momentum REAL;
```
Both columns are nullable; existing rows silently have NULL. The unique constraint `(date, ticker, strategy, source, run_id)` is unchanged.

**API layer**: The Express DB query for `/api/signals/latest` and `/api/signals/:id` already returns all columns by `SELECT *`. No route change needed. The TS `Signal` interface in `api.service.ts` gains:
```typescript
industry: string | null;
industry_momentum: number | null;
```

---

### Feature 2: Winner vs Loser Characteristic Analysis

**Current state** — the pieces exist separately:
- `_active_trades()` splits qualified trades with valid R
- `render_report()` already segments winners/losers for `compute_metrics()`
- `Trade` carries `score`, `confidence`, `strategy` at entry time
- The `metrics_json` blob in `backtest_reports` is the extensible JSON envelope
- The Express route for `/api/runs/:run_id` already manually unpacks `metrics_json` field-by-field — adding `winner_loser_analysis` follows the same pattern

**What is missing**:

1. **`Signal` → `Trade` carry-through**: `Signal.industry_momentum: Optional[float]` and `Signal.industry: Optional[str]` added as fields. `Trade.industry_momentum: Optional[float]` and `Trade.industry: Optional[str]` added. `simulate_trades()` copies them from Signal to Trade. This makes entry-time industry momentum available on every Trade for the analysis.

2. **Analysis function** in `report.py`:
```python
def winner_loser_analysis(trades: list[Trade]) -> dict:
    # Split active trades into winners (r > 0) and losers (r <= 0)
    # For each numeric dimension (score, industry_momentum, target_r, atr)
    # compute median, p25, p75 for winners vs losers
    # Return dict: {"winner_n": int, "loser_n": int, "dimensions": [...]}
```
Each dimension entry: `{"name": str, "winner_median": float|None, "loser_median": float|None, "separation": float|None}`.

3. **`render_report()` addition**: Call `winner_loser_analysis(qualified_trades)` and include the result in `json_out` under key `"winner_loser_analysis"`.

4. **Express route**: In `runs.js`, add `result.winner_loser_analysis = reportData.winner_loser_analysis || null` in the existing unpack block. No schema change — it goes in the existing `metrics_json` blob.

5. **Angular TS interface**: `Run.winner_loser_analysis?: WinnerLoserAnalysis | null`. Add a display section in the backtests component.

---

## Data Flow

### Live Scan → Signal Display

```
scan.py scan
    ↓
data_store.get_market_data()          ← loads SPY + sector ETFs + NEW industry ETFs
    ↓
core.make_contexts()
    ├─ _make_quality_info(ticker)     ← yf.info['sector', 'industry'] fetched here
    └─ EvalContext(quality=...,
                   market_data=...)
    ↓
strategy.evaluate(ticker, df, ctx)   ← unchanged gate logic
    ↓
core.run_scan() post-processing block
    ├─ targets.attach_risk()          ← unchanged
    ├─ compute_confidence()           ← unchanged
    ├─ _ath_zone()                    ← unchanged
    └─ _industry_momentum(            ← NEW: same block, same pattern
           quality.industry,
           ctx.market_data)
    ↓
DataFrame row with industry, industry_momentum columns
    ↓
store_db.insert_signals_batch()       ← writes new columns (v9 schema)
    ↓
SQLite signals table
    ↓
Express GET /api/signals/latest       ← SELECT * returns new columns automatically
    ↓
Angular candidates page               ← new fields on Signal interface, display in table
```

### Backtest → Winner/Loser Report

```
scan.py backtest
    ↓
backtest.generate_signals()
    ├─ _quality_loader(ticker)         ← quality.industry populated
    ├─ full_market = get_market_data() ← includes industry ETFs
    └─ per day×ticker inner loop:
        ├─ strategy.evaluate()         ← unchanged
        └─ _industry_momentum()        ← NEW: same as live scan
    ↓
list[Signal] with industry_momentum   ← Signal dataclass has new fields
    ↓
simulate_trades(signals, bars)        ← copies industry_momentum to Trade
    ↓
list[Trade] with industry_momentum
    ↓
report.render_report(signals, trades)
    ├─ compute_metrics()               ← unchanged
    ├─ bucket_by_score()               ← unchanged
    ├─ gate_attribution()              ← unchanged
    ├─ stop_out_forensics()            ← unchanged
    └─ winner_loser_analysis()         ← NEW: takes qualified_trades
    ↓
json_out["winner_loser_analysis"] = {...}
    ↓
store_db.insert_backtest_report(      ← json.dumps(json_out) → metrics_json blob
    run_id, json_out, biases)
    ↓
Express GET /api/runs/:run_id
    result.winner_loser_analysis =    ← NEW: unpack from metrics_json
        reportData.winner_loser_analysis || null
    ↓
Angular backtests page                ← new WinnerLoserAnalysis section
```

---

## Recommended Project Structure Changes

```
scanner/
  core.py              ← ADD: INDUSTRY_ETF_MAP dict
                       ← ADD: industry field to QualityInfo dataclass
                       ← ADD: _industry_momentum() helper function
                       ← MOD: _make_quality_info() fetches .info['industry']
                       ← MOD: run_scan() post-processing block adds industry cols

  data_store.py        ← MOD: _MARKET_SYMBOLS list extended with industry ETFs
                          (XSD, KRE, KBE, XOP, XBI, XRT, ITA, XHB, IHI, KIE)

  store_db.py          ← MOD: _DDL adds industry/industry_momentum columns
                       ← MOD: migrate() adds v9 ALTER TABLE steps
                       ← MOD: insert_signal() / insert_signals_batch() include
                          new column names

  simulate.py          ← MOD: Signal dataclass adds industry, industry_momentum
                       ← MOD: Trade dataclass adds industry, industry_momentum
                       ← MOD: simulate_trades() copies fields from Signal → Trade

  backtest.py          ← MOD: Signal() construction includes new fields
                          (industry, industry_momentum from ctx.quality + market_data)

  report.py            ← ADD: winner_loser_analysis(trades) function
                       ← MOD: render_report() calls it; adds to json_out

web/
  api/routes/runs.js   ← MOD: unpack winner_loser_analysis from metrics_json blob

  ui/src/app/
    services/api.service.ts           ← MOD: Signal interface + Run interface
    pages/backtests/backtests.ts      ← MOD: display winner_loser_analysis section
    pages/candidates/candidates.ts    ← MOD: display industry + industry_momentum
```

---

## Architectural Patterns

### Pattern 1: Parquet ETF Cache Extension

**What:** `_MARKET_SYMBOLS` in `data_store.py` is a flat list. Adding industry ETF symbols extends it with zero structural change. `get_market_data()` loops over the list and returns a `dict[str, pd.DataFrame]`. `market_data.get("XSD")` returns the semiconductors ETF frame or `None` if not cached.

**When to use:** Any new benchmark ETF to be used in the scanner. The existing refresh path, split detection, and caching logic applies automatically.

**Trade-off:** All symbols in `_MARKET_SYMBOLS` are refreshed on every `scan.py refresh` call. Adding ~10 industry ETFs adds ~10 network calls per refresh. Acceptable at this scale.

### Pattern 2: Nullable Column with Schema Migration

**What:** New signal attributes are added as nullable columns with `ALTER TABLE signals ADD COLUMN ... DEFAULT NULL` in an incremental migration. Existing rows have NULL. New rows populate the field when data is available.

**When to use:** Any new per-signal attribute that is display-only and may not always be computable (e.g., industry not in ETF map → NULL momentum). The NULL signals "no data" cleanly without breaking existing queries.

**Do not use:** If the attribute must always be present for logic to be correct. Gates and score formulas are not candidates.

### Pattern 3: JSON Blob for Report Extension

**What:** `backtest_reports.metrics_json` is a single JSON blob (from `json.dumps(json_out)` in `render_report()`). Adding a new analysis section means adding a key to `json_out` in Python and unpacking it by name in the Express route. No schema change to `backtest_reports`.

**When to use:** New analysis sections in backtest reports. Avoids schema changes for each new analytical view.

**Trade-off:** The Express route (`runs.js`) must manually list each expected key. Adding `winner_loser_analysis` requires a one-line addition there and in the TypeScript `Run` interface. This is intentional — it keeps the API contract explicit.

### Pattern 4: Pre-computation Before Inner Loop (backtest only)

**What:** `generate_signals()` pre-loads all data before the `for day in trading_days` loop. Industry ETF momentum series are computed once per ticker using `_precompute_bars()` or analogously. Inside the loop, `.asof(as_of_ts)` looks up the value in O(log n).

**When to use:** Any new per-ticker time-series computation in the backtest. Adding industry momentum computation to `_precompute_bars()` or as a separate per-ticker pre-computation step avoids O(days × tickers) recomputation.

**Important:** Industry ETF frames are in `full_market` which is already pre-loaded outside the loop. The industry momentum computation for a given ticker just needs `full_market.get(etf_symbol)` — this is already available.

---

## Anti-Patterns

### Anti-Pattern 1: Computing Industry Momentum at Report Time

**What people do:** Add industry momentum as a post-hoc join at report generation time (look up sector ETF returns for each signal's date after the fact).

**Why it's wrong:** The winner/loser analysis compares entry-time momentum. If momentum is recomputed at report time using current (not historical) ETF data, you reintroduce look-ahead bias. The existing bias disclosure already calls out fundamentals look-ahead; adding price look-ahead would be a more serious distortion.

**Do this instead:** Compute industry momentum inside the scan/backtest loop at `as_of` date, store it on the signal, and carry it through to the trade. The value stored in the DB represents exactly what was observable at signal time.

### Anti-Pattern 2: New Table for Industry Classification

**What people do:** Create a separate `ticker_metadata` table for industry/sector classification.

**Why it's wrong:** The existing pattern stores `quality.sector` (and now `quality.industry`) on each signal row. Industry classification can change over time (reclassification events). Storing it per-signal preserves historical accuracy. A separate table with one row per ticker would give the current classification to all historical signals — the same look-ahead issue already acknowledged for `sector`.

**Do this instead:** Add `industry TEXT` to the `signals` table. Same as `sector` is implicit via `quality_info` but not explicitly stored (the new `industry` column makes it explicit and queryable).

### Anti-Pattern 3: Changing the EvalContext Dataclass for Industry Momentum

**What people do:** Add `industry_momentum: Optional[float]` as a field on `EvalContext` to make it available to strategies.

**Why it's wrong:** `EvalContext` is the input to strategy evaluation. Strategy `evaluate()` functions should not receive industry momentum — it's a display field, not a gate input. Adding it to `EvalContext` invites future accidental use as a gate before backtest evidence exists.

**Do this instead:** Compute industry momentum in the post-evaluation block of `run_scan()` and `generate_signals()` — the same block that computes `ath_zone` and `confidence`. Both `quality.industry` and `ctx.market_data` are accessible there without modifying `EvalContext`.

---

## Build Order (Dependencies)

The dependency chain flows top to bottom. Each phase depends on the one above it.

```
Phase 1: Data Layer
  ├─ Add industry ETF symbols to data_store._MARKET_SYMBOLS
  ├─ Add industry to QualityInfo dataclass (core.py)
  ├─ Add industry fetch in _make_quality_info() (core.py)
  └─ Add INDUSTRY_ETF_MAP dict to core.py

Phase 2: Computation Helper
  └─ Add _industry_momentum(industry, market_data) to core.py
     (Depends on: Phase 1 — needs INDUSTRY_ETF_MAP + ETF frames in market_data)

Phase 3: Signal Pipeline Wiring
  ├─ run_scan() post-block: call _industry_momentum(), add to row dict (core.py)
  ├─ generate_signals() inner loop: call _industry_momentum() (backtest.py)
  └─ Signal dataclass: add industry, industry_momentum fields (simulate.py)
     (Depends on: Phase 2)

Phase 4: DB Schema v9
  ├─ Add ALTER TABLE migrations in store_db.migrate() (store_db.py)
  └─ Update insert_signal() / insert_signals_batch() column lists (store_db.py)
     (Depends on: Phase 3 — schema matches what pipeline now produces)

Phase 5: API + Angular (industry display)
  ├─ Express: no route change needed (SELECT * already returns new columns)
  ├─ TS Signal interface: add industry, industry_momentum (api.service.ts)
  └─ Angular candidates component: add industry momentum column/indicator
     (Depends on: Phase 4)

Phase 6: Winner/Loser Analysis
  ├─ Trade dataclass: add industry, industry_momentum (simulate.py)
  ├─ simulate_trades(): copy fields from Signal → Trade (simulate.py)
  ├─ Add winner_loser_analysis() function to report.py
  ├─ render_report(): call it, add to json_out (report.py)
  ├─ Express runs.js: unpack winner_loser_analysis from metrics_json
  ├─ TS Run interface: add winner_loser_analysis field (api.service.ts)
  └─ Angular backtests component: render winner/loser comparison table
     (Depends on: Phase 3 for industry_momentum on Trade;
      Phase 4 for DB to store the new report section)
```

The entire chain can be built across two phases: Phases 1–5 as "industry display on signals", Phase 6 as "winner/loser analysis in backtest report".

---

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `core.py` ↔ `data_store.py` | `get_market_data()` returns `dict[str, pd.DataFrame]` | Adding ETF symbols to `_MARKET_SYMBOLS` is the only change needed here |
| `core.py` ↔ strategies | `EvalContext` passed in — do NOT add industry momentum here | Industry momentum is post-evaluation, not an input to gate logic |
| `backtest.py` ↔ `simulate.py` | `Signal` dataclass carries entry-time data to `simulate_trades()` | New fields flow through `Signal → Trade` |
| `simulate.py` ↔ `report.py` | `list[Trade]` passed to `render_report()` | `winner_loser_analysis()` consumes `Trade.industry_momentum` |
| `report.py` ↔ `store_db.py` | `insert_backtest_report(run_id, json_out, biases)` — JSON blob | No schema change needed for new analysis sections |
| `store_db.py` ↔ Express | Express reads via `better-sqlite3` in `db.js` | `SELECT *` on signals table automatically returns new columns |
| Express ↔ Angular | Typed REST JSON; `Signal` and `Run` interfaces in `api.service.ts` | Both must be updated when new fields are added |

### yfinance Call Budget

`_make_quality_info()` already calls `yf.Ticker(ticker).info` once per ticker and reads both `sector` and `market_cap` from the same response. Adding `industry` is a zero-cost addition — it reads the same dict: `info.get('industry')`. No new network call.

The new industry ETFs added to `_MARKET_SYMBOLS` each require one incremental refresh call (same as current sector ETFs). With ~10 new symbols, the refresh adds ~2 seconds at 0.2s pause.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Where to compute momentum | HIGH | `ath_zone` is the exact precedent; same block, same pattern |
| ETF cache extension | HIGH | `_MARKET_SYMBOLS` mechanism is straightforward |
| DB schema approach | HIGH | Six prior migrations confirm the pattern is stable |
| Industry ETF mapping completeness | MEDIUM | yfinance industry name strings are not officially documented; mapping needs empirical validation against live tickers |
| Winner/loser analysis impl | HIGH | Existing `bucket_by_score` is the template; same data, different grouping |
| Angular display | HIGH | Existing signal table already handles nullable numeric fields |

---

## Sources

- Direct codebase reading: `scanner/core.py`, `scanner/data_store.py`, `scanner/store_db.py`, `scanner/backtest.py`, `scanner/simulate.py`, `scanner/report.py`
- API contract: `web/api/routes/signals.js`, `web/api/routes/runs.js`, `web/ui/src/app/services/api.service.ts`
- Project requirements: `.planning/PROJECT.md`

---
*Architecture research for: TraderAssist industry momentum integration*
*Researched: 2026-06-30*
