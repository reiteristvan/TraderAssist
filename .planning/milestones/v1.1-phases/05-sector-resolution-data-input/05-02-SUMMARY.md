---
phase: 05-sector-resolution-data-input
plan: 02
subsystem: data
tags: [pandas, sector-filter, universe, seasonality]

# Dependency graph
requires:
  - "scanner/sector_store.py — get_sector (from 05-01)"
provides:
  - "scanner/seasonality.py — sector resolution, universe filtering, and history-validation pipeline (valid_sectors, resolve_sector, universe_path, resolve_sector_universe, validate_history, load_sector_dataset, SectorDataset)"
affects: [05-03-sector-resolution-data-input, 06-weekly-seasonality-statistics]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Skip-and-log ok/skipped report shape (copied from universe.audit_universe) reused across sector-filter and history-validation stages"
    - "Sector validated first in load_sector_dataset so invalid input raises before any universe/history work runs"

key-files:
  created:
    - scanner/seasonality.py
    - tests/test_seasonality.py
  modified: []

key-decisions:
  - "universe_path uses an explicit 4-entry whitelist dict (no raw-arg Path interpolation) — the path-traversal mitigation for T-05-03"
  - "resolve_sector derives valid names solely from SECTOR_ETF_MAP (no second hardcoded sector list), per D-02"
  - "≥2yr admission in validate_history is computed on raw get_history() output before any --years trim, per D-05/D-06"
  - "A ticker resolved to a different (non-matching) sector is dropped silently, not recorded as skipped — only unresolved sectors go into the skip report"

requirements-completed: [SEAS-01, SEAS-02, SEAS-03, SEAS-04, SEAS-05]

coverage:
  - id: D1
    description: "resolve_sector('technology') returns 'Technology' case-insensitively; unknown sector raises ValueError listing all 11 GICS names"
    requirement: "SEAS-01, SEAS-02"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_resolve_sector_case_insensitive"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_resolve_sector_unknown_lists_all_names"
        status: pass
    human_judgment: false
  - id: D2
    description: "universe_path maps sp400/sp500/sp600/all to fixed whitelisted paths; unknown or path-traversal input raises ValueError"
    requirement: "SEAS-01"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_universe_path_valid_mappings"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_universe_path_unknown_raises"
        status: pass
    human_judgment: false
  - id: D3
    description: "resolve_sector_universe matches tickers in the target sector, drops different-sector tickers silently, and records unresolved-sector tickers as skipped"
    requirement: "SEAS-01"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_resolve_sector_universe_matched_dropped_skipped"
        status: pass
    human_judgment: false
  - id: D4
    description: "validate_history admits >=2yr raw-history tickers, skips <2yr as 'insufficient-history', skips get_history-None as 'no-data' without aborting the batch, and trims admitted frames by --years after the raw-history admission check"
    requirement: "SEAS-03, SEAS-04, SEAS-05"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_validate_history_admits_long_history"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_validate_history_skips_insufficient_history"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_validate_history_skips_no_data"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_validate_history_no_data_does_not_abort_batch"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_validate_history_years_trim"
        status: pass
    human_judgment: false
  - id: D5
    description: "load_sector_dataset validates the sector first, raising ValueError before load_universe_file/get_history are ever called for an unknown sector"
    requirement: "SEAS-02"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_load_sector_dataset_invalid_sector_raises_before_get_history"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-07-09
status: complete
---

# Phase 5 Plan 2: Sector + Universe Resolution Pipeline Summary

**scanner/seasonality.py — sector-name validation, universe→ticker resolution, sector filtering via sector_store, and ≥2yr history validation reusing data_store.get_history, all with skip-not-fail semantics**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-07-09T13:57:19Z
- **Completed:** 2026-07-09T14:11:55Z
- **Tasks:** 3 completed
- **Files modified:** 2 (both new)

## Accomplishments

- `scanner/seasonality.py` created: `valid_sectors()`, `resolve_sector()`, `universe_path()`, `resolve_sector_universe()`, `validate_history()`, `load_sector_dataset()`, and the `SectorDataset` dataclass
- `resolve_sector()` is case-insensitive and derives its valid-names list solely from `SECTOR_ETF_MAP` (no second hardcoded sector list, per D-02); an unknown sector's `ValueError` message contains all 11 canonical GICS names
- `universe_path()` maps `sp400`/`sp500`/`sp600`/`all` through an explicit whitelist dict to fixed `Path` objects — the raw CLI arg is never interpolated into a path, closing the T-05-03 path-traversal threat
- `resolve_sector_universe()` filters a ticker list to one sector via `sector_store.get_sector`, dropping non-matching-sector tickers silently and recording unresolved-sector tickers in a skip report; a single `get_sector` exception is caught, logged, and treated as a skip rather than aborting the batch
- `validate_history()` layers a ≥730-day (2yr) raw-history admission check on top of `data_store.get_history()`'s existing 220-row floor; a `None` result (missing/corrupt cache) is recorded as `'no-data'` and the batch continues (SEAS-05); an admitted ticker is trimmed to `--years` only after the raw-history check passes (D-05/D-06)
- `load_sector_dataset()` orchestrates all four stages and validates the sector name FIRST, so an invalid `--sector` raises before `load_universe_file` or `get_history` are ever called (SEAS-02's "without running any analysis")
- `scanner/seasonality.py` has zero `yfinance` imports — all price data flows through the existing `data_store.get_history` cache (SEAS-03)
- 12 unit tests in `tests/test_seasonality.py` cover all five requirements; full suite grew from 245 to 257 passing tests, all green offline

## Task Commits

Each task was committed atomically:

1. **Task 1: Sector-name + universe resolution in scanner/seasonality.py** - `01f1896` (feat)
2. **Task 2: History validation + SectorDataset orchestrator** - `12451a1` (feat)
3. **Task 3: tests/test_seasonality.py** - `b52ad51` (test)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `scanner/seasonality.py` - New pipeline module: sector validation, universe resolution, sector filtering, history validation, and the `SectorDataset` orchestrator
- `tests/test_seasonality.py` - 12 unit tests covering all documented behaviors and the threat-model mitigations (whitelist path traversal guard, skip-not-fail sector/history filtering, sector-validated-first ordering)

## Decisions Made

- Followed the plan's explicit task order (implementation in Tasks 1-2, tests in Task 3) rather than a strict per-task RED/GREEN split, consistent with how Plan 01 (`sector_store.py`/`test_sector_store.py`) was structured — the plan itself organizes tasks this way
- Added one extra test beyond the plan's enumerated behaviors (`test_validate_history_no_data_does_not_abort_batch`) to explicitly prove a `None` result for one ticker in a multi-ticker batch does not prevent a subsequent good ticker from being admitted — directly exercises the SEAS-05 "batch continues" acceptance criterion with more than one ticker in play

## Deviations from Plan

None - plan executed exactly as written. All three tasks matched their `<action>`/`<verify>`/`<acceptance_criteria>` specs; no auto-fixes, no architectural changes, no auth gates.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `scanner/seasonality.py` is ready for Plan 05-03 to build the thin `seasonality_by_week.py` CLI wrapper around `load_sector_dataset()`
- `load_sector_dataset()` is also the entry point Phase 6 will call for ISO-week aggregation and bootstrap statistics on the returned `SectorDataset.frames`
- No changes to `data_store.py`, `sector_store.py`, `store_db.py`, or DB schema — purely additive, matching the phase's "no schema bump" constraint
- `pytest -q` full suite (257 tests) green offline

---
*Phase: 05-sector-resolution-data-input*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: scanner/seasonality.py
- FOUND: tests/test_seasonality.py
- FOUND commit: 01f1896
- FOUND commit: 12451a1
- FOUND commit: b52ad51
