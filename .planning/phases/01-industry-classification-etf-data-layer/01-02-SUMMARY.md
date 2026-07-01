---
phase: 01-industry-classification-etf-data-layer
plan: "02"
subsystem: scanner/core + tests/test_core
tags: [industry-classification, quality-info, tdd, offline]
status: complete

dependency_graph:
  requires:
    - Plan 01-01 (INDUSTRY_ETF_MAP, resolve_industry_etf)
  provides:
    - QualityInfo.industry (Optional[str], display name)
    - QualityInfo.industry_key (Optional[str], slug for ETF lookup)
    - _make_quality_info() extended to populate both fields from yfinance info dict
  affects:
    - Phase 2 momentum computation (consumes industry_key via resolve_industry_etf)
    - Any downstream callsite that constructs QualityInfo (all stay valid — appended with defaults)

tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN cycle (failing test committed before implementation)
    - Optional[str] = None field appended to frozen dataclass (backward-compat extension)
    - info.get() from already-fetched dict — no extra yfinance network call

key_files:
  created: []
  modified:
    - scanner/core.py
    - tests/test_core.py

decisions:
  - Fields appended last (after float_shares) so existing 5-positional-arg callsites stay valid without changes (D-04, D-05)
  - Field names industry and industry_key (no underscore suffix) — consistent with sector convention (D-05)
  - Read from info.get('industryKey') — capital K matches yfinance dict key name
  - When info is empty (rate-limited path), both fields resolve to None via info.get() — no empty string substitution

metrics:
  duration_minutes: 5
  completed_date: "2026-07-01"
  tasks_completed: 2
  files_modified: 2
---

# Phase 01 Plan 02: QualityInfo Industry Classification Fields Summary

**One-liner:** Two Optional[str] fields (industry, industry_key) appended to frozen QualityInfo dataclass and populated from the existing yfinance info dict — no new network calls.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for QualityInfo industry fields | d9dacad | tests/test_core.py |
| 1 (GREEN) | Add industry and industry_key fields to QualityInfo | 09719ac | scanner/core.py |
| 2 | Populate fields in _make_quality_info() | a7e91f9 | scanner/core.py |

## What Was Built

**QualityInfo dataclass** (`scanner/core.py`, `@dataclass(frozen=True)`):
- Added `industry: Optional[str] = None` — human-readable display name (e.g. "Semiconductors")
- Added `industry_key: Optional[str] = None` — industryKey slug for `resolve_industry_etf()` (e.g. "semiconductors")
- Both fields appended after `float_shares` so all existing 5-positional-arg callsites (`backtest.py:335`, `test_core.py:204`, `test_strategies.py:35`, `test_targets.py:95/116/131`, `test_fixtures.py:28`) remain valid

**_make_quality_info()** (`scanner/core.py`):
- Added `industry = info.get("industry")` — reads from the already-fetched info dict (D-04)
- Added `industry_key = info.get("industryKey")` — note capital K matches yfinance key (D-04)
- Both passed into `QualityInfo(...)` return as keyword args
- No new `yf.Ticker().info` call — reuses the existing 3-retry rate-limit loop's result

**Tests** (`tests/test_core.py`):
- `test_quality_info_industry_default`: asserts `QualityInfo(False, None, None, None, None).industry is None` and `.industry_key is None`
- `test_quality_info_industry_roundtrip`: explicit keyword construction round-trips correctly
- `test_quality_info_no_classification_is_none_not_empty_string`: absence yields None, not ""

## Verification

- `pytest tests/test_core.py -k industry_default -q`: 1 passed
- `pytest -q` (full suite): 220 passed (217 baseline + 3 new classification tests)
- All existing QualityInfo callsites confirmed valid: no positional-arg breakage

## Human-Check Pending

Per plan Task 2 `<human-check>`: run `python scan.py scan --strategy pullback --ticker AAPL` and ~10 representative tickers across sectors; confirm yfinance `.info['industry']` returns non-null human-readable strings (e.g. "Semiconductors", "Software—Infrastructure") whose corresponding `industryKey` matches a key in `INDUSTRY_ETF_MAP`. Network-dependent; to be verified end-of-phase. (IND-01)

## Deviations from Plan

None — plan executed exactly as written. TDD RED/GREEN cycle followed. Three tests added (plan specified the `-k industry_default` selectable test; roundtrip and no-classification tests added as additional coverage).

## Known Stubs

None — this plan adds dataclass fields and a dict read. No display rendering, no DB writes, no computed momentum values.

## Threat Surface Scan

No new network endpoints or auth paths. The only new trust boundary crossing is T-02-01 (plan threat register): untrusted classification strings from yfinance `.info` enter `QualityInfo`. Disposition: values are stored as opaque `Optional[str]` and used only as dict keys (`resolve_industry_etf`) or display text — never eval'd, path-joined, or used in SQL in this plan.

## Self-Check: PASSED

- scanner/core.py: FOUND
- tests/test_core.py: FOUND
- 01-02-SUMMARY.md: FOUND
- Commit d9dacad (RED): FOUND
- Commit 09719ac (GREEN): FOUND
- Commit a7e91f9 (Task 2): FOUND
- Full test suite: 220 passed
