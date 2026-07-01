---
phase: 02-industry-momentum-computation-schema-v7
verified: 2026-07-01T00:00:00Z
status: human_needed
score: 4/5 must-haves verified
behavior_unverified: 1
overrides_applied: 0
re_verification: false
gaps_resolved:
  - truth: "schema_version reads 7 (ROADMAP Success Criterion #1 stated version)"
    resolution: >
      ROADMAP.md Phase 2 SC#1 updated from 'reads 7' to 'reads 9'; REQUIREMENTS.md
      IND-05 updated from 'schema v7' to 'schema v9'. Both documents now match the
      implementation. Gap closed 2026-07-01.
behavior_unverified_items:
  - truth: >
      A backtest spot-check on a specific historical date confirms the ETF close price
      used equals the actual historical close on that date — no future prices consumed
    test: >
      Run `python scan.py backtest --strategy pullback --file universes/sample.txt
      --start 2024-01-01 --end 2024-06-30 --out runs/ind_check/`,
      then ingest via journal and query a specific signal date.
    expected: >
      The stored industry_momentum for that date equals
      (ETF_Close[date] / ETF_Close[date-20] - 1) * 100
      computed manually from yfinance historical closes — confirming no future ETF
      prices leaked into the stored value.
    why_human: >
      The slicing mechanism (sliced_market = {sym: df[df.index <= as_of_ts] ...}) is
      verified by code inspection and by test_industry_no_lookahead_backtest using
      synthetic data. The specific historical-date accuracy check against real yfinance
      prices requires a network-connected run and manual cross-reference.
human_verification:
  - test: >
      Live scan after migration: run
      `python scan.py refresh --file universes/sample.txt` then
      `python scan.py scan --strategy pullback --file universes/sample.txt`,
      then query scanner.db.
    expected: >
      SELECT version FROM schema_version returns 9;
      SELECT ticker, industry_group, industry_momentum, industry_above_50ma FROM signals
      ORDER BY created_at DESC LIMIT 10 shows non-null industry_group and signed
      industry_momentum for mapped tickers, and NULL (not 0.0) in industry_momentum
      for any unmapped ticker.
    why_human: >
      The live scanner.db is currently at schema v8 (migration is lazy — triggered by
      first write_live_signals call). A real network-connected scan is needed to confirm
      migration runs correctly against the production DB and that yfinance industry
      classification returns non-null values for sample universe tickers.
  - test: >
      Backtest historical spot-check (IND-06 with real data):
      Run `python scan.py backtest --strategy pullback --file universes/sample.txt
      --start 2024-01-01 --end 2024-06-30 --out runs/ind_check/`, then ingest the run,
      then pick a specific signal date and compare the stored industry_momentum to
      (ETF.Close[date] / ETF.Close[date-20] - 1) * 100 using real yfinance closes.
    expected: >
      Stored industry_momentum matches the manually-computed 20-day ROC from actual
      historical ETF closes, confirming no future prices were consumed.
    why_human: >
      The slicing invariant is proved by code + automated test, but 'actual historical
      close equals stored value' requires a real data run to confirm end-to-end.
---

# Phase 02: Industry Momentum Computation + Schema v9 Verification Report

**Phase Goal:** Every signal has industry group, 20-day momentum score, above/below 50-day MA flag, and rank percentile computed without look-ahead bias and stored in dedicated DB columns under schema v9.
**Verified:** 2026-07-01
**Status:** human_needed
**Re-verification:** No — initial verification (gap resolved 2026-07-01: ROADMAP/REQUIREMENTS schema version label updated from v7 to v9)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | scan.py scan produces signals with non-null `industry_group` (TEXT) and `industry_momentum` (REAL) in scanner.db | VERIFIED | store_db.py DDL (lines 66-69): all 4 columns in CREATE TABLE; insert_signal / insert_signals_batch (lines 208-260): 4 columns written via `.get()` defaults; journal.py write_live_signals (lines 68-71): 4 keys forwarded from row dict; run_scan (lines 705-716): _industry_strength called per ticker, keys attached to row |
| 2 | schema_version reads 9 (updated from stale "v7" label in ROADMAP) | VERIFIED | _SCHEMA_VERSION = 9 in store_db.py line 15. Live DB at v8 auto-migrates to v9 on first write_live_signals call. ROADMAP SC#1 and REQUIREMENTS.md IND-05 updated 2026-07-01 to reflect v9. |
| 3 | Each signal carries 20-day ETF momentum score vs SPY (IND-02), above/below 50-day MA boolean (IND-03), and industry rank percentile (IND-04) | VERIFIED | _industry_strength() (core.py 275-312): computes industry_mom_20d, industry_above_50ma, industry_rs_spy; _attach_industry_rank_pct() (core.py 315-339): post-loop rank(pct=True); backtest.py (lines 315-338): per-day ETF dict + day_rank before ticker sub-loop; all 9 industry-related tests pass |
| 4 | Backtest spot-check on a specific historical date confirms ETF close used = actual historical close — no future prices consumed | PRESENT_BEHAVIOR_UNVERIFIED | Slicing mechanism verified: backtest.py line 316-318 `sliced_market = {sym: df[df.index <= as_of_ts] ...}`; _industry_strength called with sliced_market (line 331); test_industry_no_lookahead_backtest passes with synthetic post-as_of spike. Real-data historical check is network-dependent — deferred to human verification. |
| 5 | Ticker with no matched ETF stores NULL in `industry_momentum`; NULL survives DB round-trip without coercion to 0.0 | VERIFIED | test_industry_momentum_null_round_trip (test_store_db.py lines 444-457): inserts all-None signal, re-reads, asserts industry_momentum is None (not 0.0); _industry_strength returns Python None (never NaN) for missing ETF; parameterized INSERT uses .get() defaults |

**Score:** 4/5 truths verified (1 PRESENT_BEHAVIOR_UNVERIFIED; stale schema label gap resolved 2026-07-01)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scanner/core.py` :: `_industry_strength()` | Computes 20d mom, 50MA flag, SPY ratio | VERIFIED | Lines 275-312; 4-key dict; None for missing; no yf import, no datetime.now |
| `scanner/core.py` :: `_attach_industry_rank_pct()` | Post-loop rank(pct=True) helper | VERIFIED | Lines 315-339; mutates in-place; <2 ETFs leaves None; NaN coerced to None |
| `scanner/core.py` :: `run_scan()` wiring | Row carries 4 industry keys + post-loop rank | VERIFIED | Lines 705-727; getattr guards on ctx.quality; _attach_industry_rank_pct called after loop |
| `scanner/store_db.py` :: schema v9 migration | ALTER TABLE adds 4 columns; _SCHEMA_VERSION = 9 | VERIFIED | Lines 15, 159-165; `if current < 8:` now has `current = 8` guard so v7→v9 upgrade works; DDL updated for fresh DBs |
| `scanner/store_db.py` :: insert_signal / insert_signals_batch | Persist 4 industry columns | VERIFIED | Lines 208-260; parameterized :named placeholders; .get() defaults for NULL |
| `scanner/simulate.py` :: Signal dataclass | 4 industry Optional fields appended after close | VERIFIED | Lines 30-33; all Optional[X] = None; positional calls unaffected |
| `scanner/backtest.py` :: per-day ETF momentum + rank | sliced_market only; day_rank before ticker sub-loop | VERIFIED | Lines 315-338 (sliced_market + day_etf_scores + day_rank); lines 426-449 (Signal construction with 4 industry fields) |
| `scanner/journal.py` :: write_live_signals | 4 industry keys forwarded | VERIFIED | Lines 68-71; row.get() for all 4 keys |
| `scanner/journal.py` :: backtest sig dict | s.industry_group/momentum/above_50ma/rank_pct | VERIFIED | Lines 310-313; Signal attributes read directly |
| `tests/test_core.py` :: industry_strength tests | 5 test functions | VERIFIED | test_industry_strength_basic, _no_etf_returns_none, _insufficient_bars, _above_50ma_flag, _rs_spy_ratio all present and passing |
| `tests/test_core.py` :: rank + no-look-ahead tests | 3 test functions | VERIFIED | test_industry_rank_pct_multi_etf, _single_etf_returns_none, test_industry_no_lookahead_backtest all present and passing |
| `tests/test_store_db.py` :: NULL round-trip | test_industry_momentum_null_round_trip | VERIFIED | Lines 444-457; asserts None (not 0.0) |
| `tests/test_store_db.py` :: migrate assertions | schema_version == 9; industry columns asserted | VERIFIED | test_migrate_idempotent (v == 9), test_migrate_schema_version_present (== 9), test_migrate_v1_to_current (== 9 + all 4 columns asserted) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ctx.market_data` (sliced to as_of) | `_industry_strength()` | call in run_scan line 711 | VERIFIED | getattr guards on ctx.quality |
| `_industry_strength()` | `row["industry_momentum"]` | run_scan line 714 | VERIFIED | strength["industry_mom_20d"] assigned |
| `rows` (assembled) | `_attach_industry_rank_pct(rows)` | run_scan line 727 | VERIFIED | post-loop, before pd.DataFrame(rows) |
| `run_scan` row dict | `write_live_signals` sig dict | journal.py lines 68-71 | VERIFIED | row.get("industry_group") etc. |
| `sliced_market` (index <= as_of_ts) | `_industry_strength()` in backtest | backtest.py line 331 | VERIFIED | NOT full_market |
| `day_etf_scores` (per-day ETF dict) | `day_rank` | backtest.py line 338 | VERIFIED | rank(pct=True) before ticker sub-loop |
| `Signal.industry_*` fields | backtest sig dict | journal.py lines 310-313 | VERIFIED | s.industry_group etc. |
| `insert_signals_batch` | `signals` table industry columns | store_db.py lines 233-260 | VERIFIED | parameterized INSERT |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `run_scan()` row | `industry_momentum` | `_industry_strength()` → `market_data[etf_ticker]["Close"]` (already-sliced Parquet cache) | Yes — real ETF closes from Parquet | FLOWING |
| `_attach_industry_rank_pct()` | `industry_rank_pct` | `pd.Series(etf_scores).rank(pct=True)` over assembled rows | Yes — derived from real ETF momentum values | FLOWING |
| `generate_signals()` Signal | `industry_momentum` | `_industry_strength(..., sliced_market)` — sliced_market from full_market[sym][index <= as_of_ts] | Yes — real historical closes sliced at as_of | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `_industry_strength` 20d ROC correct | `pytest -q -k "industry_strength_basic"` | PASS (1 passed) | PASS |
| `_industry_strength` None for no ETF | `pytest -q -k "no_etf_returns_none"` | PASS (1 passed) | PASS |
| `_industry_strength` insufficient bars | `pytest -q -k "insufficient_bars"` | PASS (1 passed) | PASS |
| `industry_above_50ma` flag True/False/None | `pytest -q -k "above_50ma"` | PASS (1 passed) | PASS |
| `_attach_industry_rank_pct` multi-ETF rank | `pytest -q -k "rank_pct_multi_etf"` | PASS (1 passed) | PASS |
| `_attach_industry_rank_pct` single-ETF stays None | `pytest -q -k "single_etf_returns_none"` | PASS (1 passed) | PASS |
| Look-ahead slicing invariant | `pytest -q -k "no_lookahead"` | PASS (1 passed) | PASS |
| NULL round-trip (no 0.0 coercion) | `pytest -q -k "industry_null"` | PASS (1 passed) | PASS |
| Schema migrates to v9, idempotent | `pytest -q -k "migrate"` | PASS (3 passed) | PASS |
| Full suite | `pytest -q` | 230 passed in 7.96s | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| IND-02 | 02-01-PLAN | 20-day momentum score (signed % vs SPY) for industry ETF | SATISFIED | `_industry_strength()` computes `industry_mom_20d` and `industry_rs_spy`; stored in `industry_momentum` column; test_industry_strength_basic and _rs_spy_ratio pass |
| IND-03 | 02-01-PLAN | Above/below 50-day MA boolean for industry ETF | SATISFIED | `_industry_strength()` computes `industry_above_50ma` as bool or None; test_industry_above_50ma_flag passes; stored in `industry_above_50ma` INTEGER column |
| IND-04 | 02-02-PLAN | Industry rank percentile (top-N%) among all industry groups in scan run | SATISFIED | `_attach_industry_rank_pct()` post-loop step in run_scan; per-day rank in backtest; test_industry_rank_pct_multi_etf and _single_etf_returns_none pass |
| IND-05 | 02-01-PLAN | Dedicated columns in signals table | SATISFIED (label deviation) | `industry_group`, `industry_momentum`, `industry_above_50ma`, `industry_rank_pct` in DDL and migration block; schema is v9 not v7 as written in REQUIREMENTS.md — stale planning label |
| IND-06 | 02-01-PLAN, 02-02-PLAN | No look-ahead bias — ETF price anchored to as_of | SATISFIED (mechanism) | Live path: ctx.market_data already sliced by get_market_data(end=as_of); backtest path: sliced_market={sym: df[df.index <= as_of_ts]}; test_industry_no_lookahead_backtest passes; real-data spot-check deferred to human |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | None found |

No TBD, FIXME, or XXX markers in any phase-modified file. No unreferenced debt markers.

### Human Verification Required

#### 1. Live Scan DB Migration + Industry Column Population

**Test:** Run `python scan.py refresh --file universes/sample.txt` then `python scan.py scan --strategy pullback --file universes/sample.txt`. After completion, query scanner.db: `SELECT version FROM schema_version` and `SELECT ticker, industry_group, industry_momentum, industry_above_50ma FROM signals ORDER BY created_at DESC LIMIT 10`.

**Expected:** schema_version = 9; mapped tickers show non-null `industry_group` (e.g. "Semiconductors") and a signed float in `industry_momentum`; any ticker with no industry ETF mapping shows SQL NULL (not 0.0) in `industry_momentum`.

**Why human:** The live scanner.db is currently at schema v8 (the lazy migration triggers on first write_live_signals call). A network-connected run is needed to confirm: (a) migration completes without error, (b) yfinance `.info['industry']` / `.info['industryKey']` returns non-null values for sample universe tickers, and (c) industry ETF Parquet data is available for momentum computation.

#### 2. Backtest Historical Spot-Check (IND-06 Real-Data Confirmation)

**Test:** Run `python scan.py backtest --strategy pullback --file universes/sample.txt --start 2024-01-01 --end 2024-06-30 --out runs/ind_check/`. Pick a specific signal row for a known-industry ticker on a specific date. Manually compute `(ETF.Close[date] / ETF.Close[date-20] - 1) * 100` using real yfinance historical closes and compare to the `industry_momentum` stored in scanner.db for that row.

**Expected:** Stored `industry_momentum` matches the manually-computed 20-day ROC from actual historical closes within floating-point rounding, confirming no future ETF prices were consumed.

**Why human:** The slicing mechanism (`df[df.index <= as_of_ts]`) is proved correct by code inspection and by `test_industry_no_lookahead_backtest` using synthetic data. The test with a synthetic spike confirms the mechanism works, but only a real-data run can confirm that the Parquet cache provides accurate historical closes aligned with yfinance's own API output for the same dates.

### Gaps Summary

**Gap resolved 2026-07-01:** The ROADMAP Phase 2 Success Criterion #1 originally stated "`schema_version` reads 7". This was a stale planning label — the implementation correctly used v9 (v7 consumed by `target_r`/`target_atr`, v8 by `mae_r`/`mfe_r` in prior milestone). Both ROADMAP.md and REQUIREMENTS.md IND-05 have been updated to reference v9. No implementation changes required.

---

_Verified: 2026-07-01_
_Verifier: Claude (gsd-verifier)_
