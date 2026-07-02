---
phase: 01-industry-classification-etf-data-layer
verified: 2026-07-01T00:00:00Z
status: passed
score: 7/9 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Run `python scan.py refresh --file universes/sample.txt` and confirm Parquet files for all 17 new ETFs appear under data/ohlcv/ (XSD.parquet, XSW.parquet, XBI.parquet, XPH.parquet, XHE.parquet, XHS.parquet, KRE.parquet, KBE.parquet, KIE.parquet, KCE.parquet, XHB.parquet, XRT.parquet, XAR.parquet, XOP.parquet, XES.parquet, GDX.parquet, XME.parquet) with no download errors logged."
    expected: "17 new Parquet files created under data/ohlcv/ with valid OHLCV bars. No 'Empty response' or retry-exhausted errors in output."
    why_human: "Requires live yfinance network download; cannot verify without network access."
  - test: "Run `python scan.py scan --strategy pullback --ticker AAPL` and ~9 additional representative tickers across sectors (e.g. MSFT, JPM, UNH, AMZN, LMT, XOM, NEM, DHI, KRE-tracked bank). For each, confirm that QualityInfo.industry and QualityInfo.industry_key are non-null and that industry_key appears as a key in INDUSTRY_ETF_MAP."
    expected: "Non-null industry strings (e.g. 'Semiconductors', 'Software—Infrastructure') and industryKey slugs (e.g. 'semiconductors', 'software-infrastructure') matching at least 8 of 10 tickers to INDUSTRY_ETF_MAP entries. Missing industry data (None) is acceptable only for tickers yfinance genuinely does not classify."
    why_human: "Requires live yfinance .info API call for each ticker; offline mocks cannot prove real industry classification strings are returned and mapped correctly."
---

# Phase 1: Industry Classification + ETF Data Layer Verification Report

**Phase Goal:** The pipeline knows each ticker's industry group and the industry ETF price series are Parquet-cached and ready for momentum computation.
**Verified:** 2026-07-01
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `resolve_industry_etf('semiconductors', 'Technology')` returns `'XSD'` (D-01, D-07) | VERIFIED | Test `test_resolve_industry_etf_direct_hit` passes; code at core.py:117-118 returns `INDUSTRY_ETF_MAP.get('semiconductors')` = `'XSD'` |
| 2 | `resolve_industry_etf(None, 'Technology')` returns `None` immediately — no sector fallback (D-06) | VERIFIED | Test `test_resolve_industry_etf_none_industry_key` passes; code at core.py:115-116 short-circuits on `None` |
| 3 | `resolve_industry_etf('unmapped-key', 'Technology')` returns `'XLK'` via `SECTOR_ETF_MAP` fallback (D-07); covers SC4 | VERIFIED | Test `test_resolve_industry_etf_unknown_key_sector_fallback` passes; code at core.py:118-120 falls through to `SECTOR_ETF_MAP.get(sector)` |
| 4 | All 17 new ETFs from `INDUSTRY_ETF_MAP` in `_MARKET_SYMBOLS`; no duplicates; `XLE` and `XLB` each appear exactly once (D-02) | VERIFIED | `python -c "..."` confirms 29 symbols total, `len(s)==len(set(s))`, all 17 new ETFs present, XLE count=1, XLB count=1 |
| 5 | `QualityInfo(False, None, None, None, None).industry is None` and `.industry_key is None` — 5-arg callsites stay valid (D-04, D-05) | VERIFIED | Test `test_quality_info_industry_default` passes; fields appended after `float_shares` with `= None` defaults at core.py:200-201 |
| 6 | `_make_quality_info()` reads `info.get('industry')` and `info.get('industryKey')` from the already-fetched `info` dict — no extra yfinance call (D-04) | VERIFIED | AST check confirms both `get` calls and both keyword args in `QualityInfo(...)` return; code at core.py:438-443 reuses the same `info` dict from the 3-retry loop |
| 7 | A ticker with no industry classification yields `QualityInfo.industry is None` (not empty string or 0.0) — SC3 | VERIFIED | Tests `test_quality_info_industry_default` and `test_quality_info_no_classification_is_none_not_empty_string` both pass; `info.get(...)` on an empty dict returns `None`, not `""` |
| 8 | Fetching `.info['industry']` / `.info['industryKey']` via yfinance for 10 representative tickers returns non-null strings whose `industryKey` values match `INDUSTRY_ETF_MAP` keys — SC1 | HUMAN NEEDED | Network-dependent; requires live yfinance API. Cannot verify offline. Explicitly deferred as `<human-check>` in 01-02-PLAN.md. |
| 9 | All 17 new industry ETF tickers are Parquet-cached on `scan.py refresh` without download errors — SC2 | HUMAN NEEDED | Network-dependent; requires live yfinance download. Cannot verify offline. Explicitly deferred as `<human-check>` in 01-01-PLAN.md. |

**Score:** 7/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scanner/core.py` — `INDUSTRY_ETF_MAP` | dict with ≥30 industryKey entries → ETF ticker | VERIFIED | 33 keys, 19 unique ETF values; sector-fallback entries explicit in map (D-03) |
| `scanner/core.py` — `resolve_industry_etf()` | Module-level function, importable, D-06/D-07 chain | VERIFIED | Exists at lines 113-120; importable via `from scanner.core import resolve_industry_etf` |
| `scanner/data_store.py` — `_MARKET_SYMBOLS` | Deduplicated 29-entry list including 17 new ETFs | VERIFIED | 29 symbols: 12 original (SPY + 11 sectors) + 17 new industry ETFs; zero duplicates |
| `tests/test_core.py` — resolver tests | 6 tests selectable via `-k resolve_industry_etf` | VERIFIED | All 6 cases present and passing: direct hit, sector-fallback-in-map, None key, unknown-key-sector-fallback, unknown-key-no-sector, unknown-key-bad-sector |
| `scanner/core.py` — `QualityInfo.industry` and `.industry_key` | `Optional[str] = None` fields appended after `float_shares` | VERIFIED | Lines 200-201; both default to `None`; frozen dataclass backward-compatible |
| `tests/test_core.py` — `QualityInfo` None-default tests | At least one test selectable via `-k industry_default` | VERIFIED | Three tests added: `test_quality_info_industry_default`, `test_quality_info_industry_roundtrip`, `test_quality_info_no_classification_is_none_not_empty_string` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `INDUSTRY_ETF_MAP.get(industry_key)` | `SECTOR_ETF_MAP.get(sector)` | `resolve_industry_etf()` fallback chain (D-07) | VERIFIED | Code at core.py:117-120: direct map lookup → sector fallback → `None`; all six edge cases tested |
| `_MARKET_SYMBOLS` list | Industry ETF Parquet files via `get_market_data()` | `get_market_data()` iterates `_MARKET_SYMBOLS` | VERIFIED | `get_market_data()` at data_store.py:290-297 calls `get_history(sym)` for each symbol in `_MARKET_SYMBOLS`; no literal coupling to old list |
| `_make_quality_info()` info dict | `QualityInfo.industry` and `.industry_key` | `info.get('industry')` / `info.get('industryKey')` at core.py:438-439 | VERIFIED | Same `info` dict fetched in 3-retry loop; both fields passed as keyword args to `QualityInfo(...)` return |
| 5-positional-arg `QualityInfo` callsites | New fields default to `None` | `Optional[str] = None` appended after `float_shares` | VERIFIED | `backtest.py:335`, `test_core.py` (line 204-style), `test_strategies.py:35`, `test_targets.py:95/116/131`, `test_fixtures.py:28` all valid; full suite 221 passed |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| resolve_industry_etf chain — all 6 cases | `pytest tests/test_core.py -k resolve_industry_etf -q` | 6 passed | PASS |
| QualityInfo None-default tests | `pytest tests/test_core.py -k "industry_default or industry_roundtrip or no_classification" -q` | 3 passed (9 total with resolver) | PASS |
| Full offline test suite | `pytest -q` | 221 passed | PASS |
| _MARKET_SYMBOLS dedup + new ETF presence | `python -c "..."` inline check | 29 symbols, no duplicates, all 17 new ETFs, XLE/XLB each ×1 | PASS |
| INDUSTRY_ETF_MAP key count ≥ 30 | `python -c "from scanner.core import INDUSTRY_ETF_MAP; print(len(INDUSTRY_ETF_MAP))"` | 33 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| IND-01 | 01-01-PLAN.md, 01-02-PLAN.md | Every signal shows the industry group name from yfinance `info['industry']` | SATISFIED | `QualityInfo.industry` (human-readable name) and `QualityInfo.industry_key` (slug) are populated from the `info` dict in `_make_quality_info()`; every `EvalContext` carries them. Display in CLI/UI is Phase 3 (IND-07). Classification infrastructure complete. |

No orphaned requirements: REQUIREMENTS.md traceability maps only IND-01 to Phase 1. All other requirements (IND-02 through WLA-06) are mapped to Phases 2-4.

### Anti-Patterns Found

None. Scanned `scanner/core.py`, `scanner/data_store.py`, and `tests/test_core.py` for TBD, FIXME, XXX, TODO, HACK, PLACEHOLDER patterns. Zero matches in any file modified by this phase.

### Human Verification Required

#### 1. Industry ETF Parquet Cache — Network Validation (SC2)

**Test:** Run `python scan.py refresh --file universes/sample.txt` from the project root.
**Expected:** All 17 new ETF tickers (XSD, XSW, XBI, XPH, XHE, XHS, KRE, KBE, KIE, KCE, XHB, XRT, XAR, XOP, XES, GDX, XME) produce `.parquet` files under `data/ohlcv/` with no "Empty response" or retry-exhausted error messages in output.
**Why human:** Requires live yfinance downloads; offline tests use mocked/cached frames. The mechanism is proven correct (get_market_data iterates _MARKET_SYMBOLS which contains all 17 ETFs) but actual file creation depends on network availability.

#### 2. Live industryKey Mapping Coverage — yfinance API Validation (SC1)

**Test:** Run `python scan.py scan --strategy pullback --ticker AAPL` (or modify to print QualityInfo) for 10 representative tickers across sectors: e.g. AAPL (Technology), MSFT (Technology/Software), JPM (Financial Services), UNH (Healthcare), AMZN (Consumer Cyclical), LMT (Industrials), XOM (Energy), NEM (Basic Materials), DHI (Consumer Cyclical/Construction), plus one regional bank.
**Expected:** For each ticker, `QualityInfo.industry_key` returns a non-null slug (e.g. `'semiconductors'`, `'software-infrastructure'`, `'banks-diversified'`) that appears as a key in `INDUSTRY_ETF_MAP`. At minimum 8 of 10 tickers should resolve to a direct INDUSTRY_ETF_MAP entry.
**Why human:** Requires live yfinance `.info` API calls. The `industryKey` field availability depends on yfinance ≥ 0.2.18 and the ticker's classification in Yahoo Finance's data. Cannot verify via offline mocks.

### Gaps Summary

No gaps. All offline-verifiable must-haves are confirmed in the codebase. The two items requiring human verification are network-dependent checks that were explicitly planned as end-of-phase human-checks in both PLAN files. The code infrastructure is complete and correctly wired — the human checks validate that the live data source (yfinance) behaves as expected, not that the code is correct.

---

_Verified: 2026-07-01_
_Verifier: Claude (gsd-verifier)_
