# Phase 2: Industry Momentum Computation + Schema v7 - Research

**Researched:** 2026-07-01
**Domain:** pandas time-series computation, SQLite schema migration, look-ahead bias prevention, percentile ranking
**Confidence:** HIGH (all findings from direct codebase inspection)

## Summary

Phase 2 computes three industry-momentum indicators per signal — a 20-day ETF momentum score (IND-02), an above/below 50-day MA boolean (IND-03), and a within-run industry rank percentile (IND-04) — then persists them in the DB under a schema version bump (IND-05), all without look-ahead bias (IND-06).

All required computation primitives already exist in the codebase. `_sector_strength()` in `scanner/core.py` is the direct template for the new `_industry_strength()` function. `INDUSTRY_ETF_MAP`, `resolve_industry_etf()`, and the industry ETF frames in `get_market_data()` were shipped in Phase 1. No new packages are needed.

**Critical finding:** The roadmap and STATE.md refer to this as a "schema v7" bump, but `store_db.py` already defines `_SCHEMA_VERSION = 8` and the migration function already reaches `current = 8`. Schemas v7 (target_r, target_atr) and v8 (mae_r, mfe_r, post_stop_reached_target, post_stop_mfe_r) were consumed after the roadmap was written. The new industry columns require a schema **v9** migration, not v7. Two existing tests (`test_migrate_idempotent`, `test_migrate_schema_version_present`) explicitly assert `ver == 8` and must be updated to assert `ver == 9`.

**Primary recommendation:** Implement `_industry_strength()` modeled on `_sector_strength()`, integrate it into both `run_scan()` and `generate_signals()`, add 4 nullable columns under schema v9, and update `insert_signal()`/`insert_signals_batch()` to persist the new fields.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IND-02 | 20-day ETF momentum score vs SPY on every signal | `_sector_strength()` pattern; 20-day ROC via `.iloc[-1] / .iloc[-21] - 1`; ETF frames already in `market_data` |
| IND-03 | Above/below 50-day MA boolean for industry ETF | `_sector_strength()` already computes `sector_above_50ma` via `rolling(50).mean()` — same approach |
| IND-04 | Industry rank percentile among all industries in the scan run | Post-loop batch computation using `pandas.Series.rank(pct=True)` on ETF momentum scores |
| IND-05 | Dedicated columns `industry_group` (TEXT) and `industry_momentum` (REAL) in schema v9 | Two `ALTER TABLE ADD COLUMN` statements; follows `ath_zone` migration precedent |
| IND-06 | No look-ahead bias — ETF data anchored to signal's `as_of` | `market_data` is already sliced to `as_of` in both `make_context()` and the backtest inner loop's `sliced_market` dict |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Industry momentum computation | scanner/core.py | scanner/backtest.py | `_sector_strength()` lives in core.py; same layer owns `_industry_strength()` |
| Look-ahead bias prevention | scanner/data_store.py | scanner/backtest.py | `get_market_data(end=as_of)` slices frames; backtest loop slices per-day |
| Industry rank percentile | scanner/core.py (run_scan) | scanner/backtest.py | Batch post-loop step; different logic in live vs backtest paths |
| DB persistence | scanner/store_db.py | scanner/journal.py | All SQL in store_db; journal.py builds dict then calls store_db |
| Signal transport (backtest) | scanner/simulate.py (Signal) | scanner/backtest.py | Signal dataclass carries fields from backtest loop to DB writer |

## Standard Stack

### Core (all already installed — no new packages)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | installed | 20-day ROC, 50-day MA, rank(pct=True) | Already used throughout; `.iloc[-1]`, `.rolling()`, `.rank(pct=True)` sufficient |
| sqlite3 (stdlib) | stdlib | Schema migration, column insert | All SQL in store_db.py per project convention |

### No New Packages

This phase introduces zero new Python dependencies. All required computation is pandas operations on DataFrames that already exist in `ctx.market_data`. The `INDUSTRY_ETF_MAP`, `resolve_industry_etf()`, and industry ETF Parquet files were shipped in Phase 1.

**Package Legitimacy Audit:** Not applicable — no new packages.

## Architecture Patterns

### System Architecture Diagram

```
Live scan path:
  run_scan() [core.py]
    ├── per-ticker: strategy_fn() → result
    ├── per-ticker: _industry_strength(industry_key, sector, ctx.market_data)
    │     ├── resolve_industry_etf() → etf_ticker
    │     ├── market_data[etf_ticker] → etf_df (already sliced to as_of)
    │     ├── market_data["SPY"]     → spy_df
    │     └── return {industry_etf, industry_mom_20d, industry_above_50ma, industry_rs_spy}
    ├── row["industry_group"]    = ctx.quality.industry  (from Phase 1)
    ├── row["industry_momentum"] = industry_mom_20d (None if no ETF match)
    ├── row["industry_above_50ma"] = industry_above_50ma
    └── POST-LOOP: add industry_rank_pct to each row via pandas rank(pct=True)
  write_live_signals() [journal.py] → insert_signals_batch() [store_db.py]

Backtest path:
  generate_signals() [backtest.py]
    ├── pre-loop: ETF frames already in full_market (from Phase 1)
    ├── per-day: sliced_market = {sym: df[df.index <= as_of_ts] ...}
    ├── per-day: compute per-ETF momentum dict for this day → rank among ETFs
    ├── per-ticker×day: look up industry_etf rank from per-day dict
    └── Signal(..., industry_group=..., industry_momentum=..., ...)
  Signal objects → scan.py cmd_backtest → store_db.insert_signals_batch()
```

### Recommended Project Structure

No new files needed. Changes touch:
```
scanner/
  core.py          # add _industry_strength(); extend run_scan() row assembly
  store_db.py      # schema v9 migration; update insert_signal/insert_signals_batch
  simulate.py      # add 4 Optional fields to Signal dataclass
  backtest.py      # integrate per-day ETF rank; attach to Signal
scanner/journal.py # extend sig dict to include industry fields
tests/
  test_core.py     # new tests for _industry_strength()
  test_store_db.py # update ver == 8 → ver == 9; add NULL round-trip test
```

### Pattern 1: `_industry_strength()` — follow `_sector_strength()`

**What:** Compute per-signal industry ETF momentum metrics from the already-sliced `market_data` dict.

**When to use:** In `run_scan()` (live path) and `generate_signals()` (backtest path) after strategy evaluation, before row assembly.

```python
# Source: modeled after _sector_strength() in scanner/core.py
def _industry_strength(
    industry_key: Optional[str],
    sector: Optional[str],
    market_data: dict,
) -> dict:
    out = {
        "industry_etf": None,
        "industry_mom_20d": None,
        "industry_above_50ma": None,
        "industry_rs_spy": None,
    }
    etf = resolve_industry_etf(industry_key, sector)
    if etf is None:
        return out
    out["industry_etf"] = etf
    etf_df = market_data.get(etf)
    spy_df = market_data.get("SPY")
    if etf_df is None or len(etf_df) < 21:
        return out                          # not enough bars for 20-day ROC
    etf_mom = float(etf_df["Close"].iloc[-1] / etf_df["Close"].iloc[-21] - 1) * 100
    out["industry_mom_20d"] = etf_mom
    if len(etf_df) >= 50:
        sma50 = etf_df["Close"].rolling(50).mean().iloc[-1]
        out["industry_above_50ma"] = bool(etf_df["Close"].iloc[-1] > sma50)
    if spy_df is not None and len(spy_df) >= 21:
        spy_mom = float(spy_df["Close"].iloc[-1] / spy_df["Close"].iloc[-21] - 1) * 100
        if spy_mom != 0:
            out["industry_rs_spy"] = etf_mom / spy_mom
    return out
```

### Pattern 2: Rank Percentile — post-loop batch step in `run_scan()`

**What:** After all per-ticker rows are assembled, compute what percentile each signal's industry ETF ranks at among all ETFs seen in this scan run.

**When to use:** In `run_scan()` after the ticker loop, before returning. NOT inside the per-ticker loop.

```python
# Source: pandas rank(pct=True) applied to ETF-level scores
# After the loop, rows is a list[dict] with "industry_etf" and "industry_momentum"

import pandas as pd

def _attach_industry_rank_pct(rows: list[dict]) -> None:
    """Mutate rows in-place: add industry_rank_pct from per-ETF percentile ranking."""
    # Collect one momentum score per unique ETF (use first signal's score — all signals
    # from the same ETF on the same scan date have the same momentum score)
    etf_scores: dict[str, float] = {}
    for row in rows:
        etf = row.get("industry_etf")
        mom = row.get("industry_momentum")
        if etf is not None and mom is not None and etf not in etf_scores:
            etf_scores[etf] = mom
    if len(etf_scores) < 2:
        # Only 1 or 0 ETFs — rank is meaningless; leave as None
        return
    etf_series = pd.Series(etf_scores)
    pct_ranks = etf_series.rank(pct=True)   # ascending; higher momentum = higher rank
    for row in rows:
        etf = row.get("industry_etf")
        if etf is not None:
            row["industry_rank_pct"] = float(pct_ranks.get(etf, float("nan")))
            if pd.isna(row["industry_rank_pct"]):
                row["industry_rank_pct"] = None
```

### Pattern 3: Schema v9 migration — follow `ath_zone` precedent

**What:** Two nullable `ALTER TABLE ADD COLUMN` statements inside an `if current < 9:` block.

**When to use:** In `store_db.migrate()` as the next migration step after the existing `current < 8` block.

```python
# Source: existing migration pattern in scanner/store_db.py
_SCHEMA_VERSION = 9  # bump from 8

# In migrate(), after the existing `if current < 8:` block:
if current < 9:
    conn.execute("ALTER TABLE signals ADD COLUMN industry_group TEXT")
    conn.execute("ALTER TABLE signals ADD COLUMN industry_momentum REAL")
    conn.execute("ALTER TABLE signals ADD COLUMN industry_above_50ma INTEGER")
    conn.execute("ALTER TABLE signals ADD COLUMN industry_rank_pct REAL")
    conn.execute("UPDATE schema_version SET version = 9")
    current = 9
```

Note: `industry_above_50ma` is INTEGER (0/1/NULL) per SQLite boolean convention (same as `qualified`). `industry_group`, `industry_momentum`, and `industry_rank_pct` store NULL when no ETF match — SQLite stores Python `None` as NULL automatically in parameterized queries.

### Pattern 4: Updating `insert_signal()` and `insert_signals_batch()`

**What:** Add the 4 new columns to the INSERT statement. Follow the `gate_detail_json`/`ath_zone` pattern — use `.get()` with implicit None default.

```python
# Source: existing insert_signal() in scanner/store_db.py — add 4 columns
def insert_signal(conn, sig):
    conn.execute(
        """INSERT OR IGNORE INTO signals
           (date, ticker, strategy, source, run_id, score, confidence,
            stop, target, atr, qualified, failed_gates, close,
            gate_detail_json, ath_zone,
            industry_group, industry_momentum, industry_above_50ma, industry_rank_pct)
           VALUES (:date, :ticker, :strategy, :source, :run_id, :score, :confidence,
                   :stop, :target, :atr, :qualified, :failed_gates, :close,
                   :gate_detail_json, :ath_zone,
                   :industry_group, :industry_momentum,
                   :industry_above_50ma, :industry_rank_pct)""",
        {
            **sig,
            "gate_detail_json": sig.get("gate_detail_json"),
            "ath_zone": sig.get("ath_zone"),
            "industry_group": sig.get("industry_group"),
            "industry_momentum": sig.get("industry_momentum"),
            "industry_above_50ma": sig.get("industry_above_50ma"),
            "industry_rank_pct": sig.get("industry_rank_pct"),
        },
    )
    conn.commit()
```

### Pattern 5: Signal dataclass extension for backtest path

**What:** Add 4 Optional fields to `Signal` in `scanner/simulate.py`. Fields appended with `None` defaults so all existing callsites constructing Signal positionally remain valid.

```python
# Source: existing Signal dataclass in scanner/simulate.py
@dataclass
class Signal:
    # ... existing fields ...
    close: float = 0.0
    # New fields — Phase 2
    industry_group: Optional[str] = None
    industry_momentum: Optional[float] = None
    industry_above_50ma: Optional[bool] = None
    industry_rank_pct: Optional[float] = None
```

### Anti-Patterns to Avoid

- **Using `float('nan')` or `numpy.nan` for missing industry_momentum**: pandas `NaN` values in a dict can coerce to `0.0` when written to SQLite depending on the driver. Always use Python `None` for absent values. The `_industry_strength()` function returns `None` (Python) for all fields when no ETF match — never `float('nan')`.
- **Computing rank_pct inside the per-ticker loop**: Rank percentile requires seeing all ETFs in the run. Computing it per-ticker produces wrong results (rank among 1 = 100%). Must be a post-loop step.
- **Re-fetching ETF price data inside the ticker loop**: `get_market_data()` is already called once before the ticker loop in both `make_contexts()` and `generate_signals()`. Never call `get_history(etf_ticker)` inside the loop — that breaks look-ahead bias prevention and is O(n×ETF).
- **Calling `datetime.now()` inside `_industry_strength()`**: The function receives an already-sliced `market_data` dict. No date computation needed inside — the slicing was already done by the caller.
- **Importing yfinance in core.py for ETF price data**: Project rule: no `yf.` imports outside `data_store.py`/`earnings_store.py`. Use `market_data.get(etf_ticker)` — the frames are already fetched and cached.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Percentile ranking | Custom sort + index / NumPy percentile | `pandas.Series.rank(pct=True)` | Handles ties correctly (averaged ranks); one-liner; already in environment |
| ETF resolution | ad-hoc if/else chains | `resolve_industry_etf()` (Phase 1) | Already implements two-tier lookup with None short-circuit (D-06, D-07) |
| Look-ahead bias prevention | Date filtering inside `_industry_strength()` | Pass already-sliced `market_data` dict | Slicing happens exactly once per scan/day in `make_context()` / backtest loop |
| Schema migration guard | Checking columns with `PRAGMA table_info` | Follow `if current < N:` pattern in `store_db.migrate()` | Existing pattern is idempotent and tested; `executescript(_DDL)` already handles fresh DB |

**Key insight:** Every computation primitive for this phase already exists — the phase is about wiring them together and persisting the results, not building new algorithms.

## Common Pitfalls

### Pitfall 1: Schema version number is NOT v7
**What goes wrong:** Planning tasks that bump schema to v7 will FAIL — `migrate()` already has an `if current < 7:` block that adds `target_r` and `target_atr`. Running it on a v8 DB would be a no-op for that block, but setting `_SCHEMA_VERSION = 7` (instead of 9) would leave the DB stuck at v8 or produce a corrupt state.
**Why it happens:** The roadmap was written when the DB was at v6. Since then, v7 (target_r, target_atr) and v8 (mae_r, mfe_r, post_stop_reached_target, post_stop_mfe_r) were added independently.
**How to avoid:** Set `_SCHEMA_VERSION = 9` and add a new `if current < 9:` migration block.
**Warning signs:** Test `test_migrate_idempotent` asserts `ver == 8` and `test_migrate_schema_version_present` asserts `ver == 8` — both must be updated to `ver == 9`.

### Pitfall 2: NaN silently coercing to 0.0 in DB
**What goes wrong:** A ticker with no industry ETF match should store `industry_momentum = NULL` in the DB. If the computation produces `float('nan')` instead of Python `None`, SQLite may store 0.0 or raise an error depending on the driver version.
**Why it happens:** Pandas operations naturally produce NaN for missing data. If `etf_df["Close"].iloc[-1] / etf_df["Close"].iloc[-21]` encounters a NaN in the series, the result is NaN not None.
**How to avoid:** In `_industry_strength()`, check `len(etf_df) < 21` before any arithmetic and return `None` explicitly. After any arithmetic, if the result is NaN, coerce to `None` before inserting.
**Warning signs:** DB round-trip test shows `industry_momentum = 0.0` for a ticker with no ETF match instead of `NULL`.

### Pitfall 3: Rank percentile computed before all tickers evaluated
**What goes wrong:** If rank is computed inside the per-ticker loop, each signal gets rank 1.0 (it's the only ETF seen so far). This passes silently.
**Why it happens:** Code author places rank computation inside the same per-ticker block as `_industry_strength()`.
**How to avoid:** Rank computation is a post-loop batch step in `run_scan()`. In the backtest, compute ETF-level momentum dict per day BEFORE the per-ticker sub-loop for that day.
**Warning signs:** All signals show `industry_rank_pct = 1.0` regardless of ETF.

### Pitfall 4: `generate_signals()` doesn't persist industry fields through Signal dataclass
**What goes wrong:** Industry fields computed in the backtest loop are not attached to `Signal` objects, so they're lost when signals are written to the DB.
**Why it happens:** Signal dataclass doesn't have industry fields yet; engineer computes momentum but has nowhere to put it.
**How to avoid:** Add 4 Optional fields to Signal before wiring up `generate_signals()`. The `scan.py` backtest command's DB writer iterates `Signal` objects — if the fields aren't on Signal, they never reach the DB.
**Warning signs:** Backtest signals in DB have `industry_group = NULL` even for well-known tickers with mapped ETFs.

### Pitfall 5: `journal.py write_live_signals()` not updated
**What goes wrong:** Even if `run_scan()` returns a DataFrame with `industry_group` and `industry_momentum` columns, `write_live_signals()` builds a hard-coded sig dict that omits these fields. They never reach `insert_signals_batch()`.
**Why it happens:** `write_live_signals()` in `journal.py` (lines 52-68) constructs the sig dict explicitly — new fields must be added there.
**How to avoid:** Add `.get("industry_group")`, `.get("industry_momentum")`, `.get("industry_above_50ma")`, `.get("industry_rank_pct")` to the sig dict in `write_live_signals()`.
**Warning signs:** Live scan DB rows show NULL for industry columns even though `run_scan()` returned correct values.

## Runtime State Inventory

This is a forward phase (not a rename or migration of existing data). No runtime state needs to be migrated. Existing signal rows in `scanner.db` will have NULL for the 4 new columns after migration — this is expected and correct. No backfill is required.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing signals rows (schema v8) | None — NULL in new columns is expected; ALTER TABLE ADD COLUMN is non-destructive |
| Live service config | None | — |
| OS-registered state | None | — |
| Secrets/env vars | None | — |
| Build artifacts | None | — |

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | None detected — runs with `pytest -q` |
| Quick run command | `pytest tests/test_core.py tests/test_store_db.py -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IND-02 | `_industry_strength()` returns correct 20-day ROC | unit | `pytest tests/test_core.py -k industry_strength -q` | No — Wave 0 |
| IND-02 | SPY ratio (industry_rs_spy) computed correctly | unit | `pytest tests/test_core.py -k industry_rs_spy -q` | No — Wave 0 |
| IND-03 | `industry_above_50ma` True when ETF close > SMA50 | unit | `pytest tests/test_core.py -k industry_above_50ma -q` | No — Wave 0 |
| IND-04 | Rank percentile batch step assigns correct percentiles | unit | `pytest tests/test_core.py -k industry_rank_pct -q` | No — Wave 0 |
| IND-04 | Single-ETF run returns None rank (< 2 ETFs) | unit | `pytest tests/test_core.py -k industry_rank_pct -q` | No — Wave 0 |
| IND-05 | Schema migration creates industry columns under v9 | unit | `pytest tests/test_store_db.py -k migrate -q` | Partial — update existing |
| IND-05 | NULL round-trip: industry_momentum=None → DB NULL | unit | `pytest tests/test_store_db.py -k industry_null -q` | No — Wave 0 |
| IND-06 | ETF frame slice boundary: spot-check on historical date | integration | `pytest tests/test_core.py -k no_lookahead -q` | No — Wave 0 |
| IND-06 | ETF close used matches actual historical close for date | manual | Run `scan.py scan --date 2024-06-01 --ticker NVDA` | N/A |

### Wave 0 Gaps

- [ ] `tests/test_core.py` — add tests: `test_industry_strength_basic`, `test_industry_strength_no_etf_returns_none`, `test_industry_strength_insufficient_bars_returns_none`, `test_industry_above_50ma_flag`, `test_industry_rs_spy_ratio`, `test_industry_rank_pct_multi_etf`, `test_industry_rank_pct_single_etf_returns_none`
- [ ] `tests/test_store_db.py` — update `test_migrate_idempotent` and `test_migrate_schema_version_present` from `ver == 8` to `ver == 9`; add `test_industry_momentum_null_round_trip`

*(Existing test infrastructure covers the pytest runner — only new test functions needed)*

### Sampling Rate

- **Per task commit:** `pytest tests/test_core.py tests/test_store_db.py -q`
- **Per wave merge:** `pytest -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | `industry_key` from yfinance info dict used only as dict key in `INDUSTRY_ETF_MAP.get()` — never eval'd, path-joined, or interpolated into SQL |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Untrusted `industry_key` from yfinance used in SQL | Tampering | Not a risk: field used only as Python dict key, never in SQL string interpolation; stored via parameterized query |
| NaN/Infinity from ETF ROC computation | Tampering | Check `len(etf_df) >= 21` before arithmetic; coerce NaN result to None before DB insert |

## Open Questions

1. **Column scope: 2 vs 4 dedicated columns**
   - IND-05 explicitly names only `industry_group` and `industry_momentum` as dedicated columns.
   - `industry_above_50ma` and `industry_rank_pct` could alternatively be stored in `gate_detail_json`.
   - Recommendation: Add all 4 as dedicated columns now — Phase 4 (winner/loser analysis) will need to query them via SQL, and storing in JSON makes that harder without re-computation.
   - If the planner wants strict IND-05 compliance, use 2 columns + gate_detail_json for the other two. But this creates rework in Phase 4.

2. **Backtest rank percentile: per-day or per-run?**
   - The REQUIREMENTS say "rank percentile among all industries in the scan run" (IND-04).
   - For a live scan (single day), this is clear: rank among all ETFs seen today.
   - For a backtest (multi-day), "scan run" could mean: all signals across all days, or all industries on each individual day. Computing daily rank is more rigorous (avoids survivorship bias across time). Recommendation: per-day rank in the backtest — compute ETF momentum dict once per day before the ticker sub-loop, then rank that day's ETFs.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pandas | All computation | Yes | installed | — |
| sqlite3 (stdlib) | Schema migration | Yes | stdlib | — |
| pytest | Test suite | Yes | installed | — |
| ETF Parquet files (XSD, XBI, etc.) | _industry_strength() | Network-dependent | — | Returns None for missing ETFs (graceful) |

**Missing dependencies with no fallback:** None — all computation works offline if Parquet files were previously cached by `scan.py refresh`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Schema v7 (per roadmap) | Schema v9 (actual) | v7 consumed for target_r/target_atr; v8 for mae_r/mfe_r | Migration block must be `if current < 9:`, constant `_SCHEMA_VERSION = 9` |
| `_sector_strength()` only | `_industry_strength()` (new) + `_sector_strength()` (unchanged) | Phase 2 | More granular ETF proxy; sector function not replaced |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 4 dedicated columns is preferable to 2 + gate_detail_json | Open Questions | Phase 4 SQL queries become harder if wrong — but no correctness risk |
| A2 | Per-day rank percentile is correct semantics for backtest | Open Questions | Rank values will differ from per-run rank; no correctness risk for Phase 2 display |

**All other claims in this document were verified by direct codebase inspection** — no assumptions made about schema version, function signatures, or existing patterns.

## Sources

### Primary (direct codebase inspection)
- `scanner/store_db.py` — confirmed `_SCHEMA_VERSION = 8`, migration blocks v1–v8, `insert_signal()` column list, `insert_signals_batch()` pattern [VERIFIED: codebase grep]
- `scanner/core.py` — confirmed `_sector_strength()` pattern, `INDUSTRY_ETF_MAP`, `resolve_industry_etf()`, `QualityInfo` fields, `run_scan()` row assembly loop [VERIFIED: codebase grep]
- `scanner/data_store.py` — confirmed `get_market_data()` returns dict of DataFrames including all 17 industry ETFs via `_MARKET_SYMBOLS`, `end=as_of` slicing [VERIFIED: codebase grep]
- `scanner/backtest.py` — confirmed `sliced_market` per-day pattern, `Signal` construction, `_make_context_from_frames()` receives pre-sliced market [VERIFIED: codebase grep]
- `scanner/simulate.py` — confirmed `Signal` dataclass fields and defaults [VERIFIED: codebase grep]
- `scanner/journal.py` — confirmed `write_live_signals()` hard-coded sig dict (lines 52-68) that must be updated [VERIFIED: codebase grep]
- `tests/test_store_db.py` — confirmed `assert ver == 8` in `test_migrate_idempotent` and `test_migrate_schema_version_present` (both require update to `ver == 9`) [VERIFIED: codebase grep]
- `.planning/REQUIREMENTS.md` — confirmed IND-02 through IND-06 scope and IND-05 explicit column names [VERIFIED: codebase grep]
- `.planning/STATE.md` — confirmed "Schema v7" decision context (made when DB was at v6; now superseded) [VERIFIED: codebase grep]

## Metadata

**Confidence breakdown:**
- Schema version finding (v9, not v7): HIGH — read directly from `_SCHEMA_VERSION = 8` in source
- Computation pattern (`_industry_strength()`): HIGH — directly modeled on existing `_sector_strength()`
- Look-ahead bias prevention: HIGH — confirmed `market_data` sliced to `as_of` in both paths
- DB insert update locations: HIGH — all three files (`store_db.py`, `journal.py`) inspected
- Rank percentile semantics: MEDIUM — two valid interpretations (per-day vs per-run); recommendation made

**Research date:** 2026-07-01
**Valid until:** Stable — only changes if store_db.py schema advances further before Phase 2 executes
