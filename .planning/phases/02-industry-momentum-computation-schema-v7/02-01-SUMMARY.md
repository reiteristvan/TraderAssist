---
phase: 02-industry-momentum-computation-schema-v7
plan: "01"
subsystem: scanner/core, scanner/store_db, scanner/journal
tags: [industry-momentum, schema-migration, tdd, live-scan]
dependency_graph:
  requires: [01-02-PLAN.md]
  provides: [_industry_strength(), schema-v9, industry-columns-in-signals]
  affects: [scanner/core.py, scanner/store_db.py, scanner/journal.py, tests/test_core.py, tests/test_store_db.py]
tech_stack:
  added: []
  patterns: [_sector_strength() template, ALTER TABLE ADD COLUMN migration, INSERT OR IGNORE with .get() defaults]
key_files:
  created: []
  modified:
    - scanner/core.py
    - scanner/store_db.py
    - scanner/journal.py
    - tests/test_core.py
    - tests/test_store_db.py
decisions:
  - schema version is 9 (v7/v8 were already consumed; v9 correct next step)
  - all missing industry values stored as Python None — never float NaN — to prevent SQLite 0.0 coercion
  - _industry_strength placed adjacent to _sector_strength in core.py
  - _DDL updated alongside migration block so fresh DBs also get the 4 columns
metrics:
  duration: "~10 minutes"
  completed: "2026-07-01"
  tasks_completed: 3
  files_modified: 5
status: complete
---

# Phase 02 Plan 01: Industry Momentum Computation + Schema v9 Summary

**One-liner:** 20-day ETF momentum (`_industry_strength`) with 50MA flag and SPY ratio, persisted in four new schema-v9 columns, wired from `run_scan()` through `write_live_signals()` to the DB.

## What Was Built

### `scanner/core.py` — `_industry_strength()`

New function adjacent to `_sector_strength()`. Accepts `industry_key`, `sector`, and `market_data` (already-sliced to `as_of`). Returns a 4-key dict:

- `industry_etf` — resolved ETF ticker (e.g., `"XSD"`) or `None`
- `industry_mom_20d` — `(close[-1]/close[-21]-1)*100` or `None` when < 21 bars
- `industry_above_50ma` — `bool(close[-1] > SMA50)` or `None` when < 50 bars
- `industry_rs_spy` — `etf_mom / spy_mom` or `None` when SPY insufficient or spy_mom == 0

All missing values are Python `None` (never `float('nan')` or `numpy.nan`). No yfinance import, no `datetime.now()` — operates on the pre-sliced `market_data` dict.

### `scanner/core.py` — `run_scan()` wiring

After `row = asdict(result)` and `row["ath_zone"] = zone_label`, `_industry_strength` is called for every ticker using `getattr` guards on `ctx.quality`. Four keys are attached to each row:
- `industry_group` (from `ctx.quality.industry`)
- `industry_etf`, `industry_momentum`, `industry_above_50ma` (from `_strength`)

`industry_rank_pct` is intentionally absent — populated in Plan 02's post-loop step.

### `scanner/store_db.py` — Schema v9

- `_SCHEMA_VERSION = 9` (bumped from 8)
- `_DDL` updated to include the 4 new columns for fresh-DB creation
- New `if current < 9:` migration block adds `industry_group TEXT`, `industry_momentum REAL`, `industry_above_50ma INTEGER`, `industry_rank_pct REAL` via `ALTER TABLE`
- `insert_signal()` and `insert_signals_batch()` extended to persist all 4 new columns using `.get()` for NULL defaults

### `scanner/journal.py` — `write_live_signals()`

Extended the hard-coded `sigs.append({...})` dict with four new `row.get()` keys: `industry_group`, `industry_momentum`, `industry_above_50ma`, `industry_rank_pct`. Values flow to `insert_signals_batch()` and therefore into the DB.

## Task Execution

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add failing tests (RED) | `93a8d98` | tests/test_core.py, tests/test_store_db.py |
| 2 | Implement _industry_strength + schema v9 (GREEN) | `116faef` | scanner/core.py, scanner/store_db.py, tests/test_store_db.py |
| 3 | Wire into run_scan + write_live_signals (GREEN) | `0f3b131` | scanner/core.py, scanner/journal.py |

## Test Results

Full suite: **227 tests, all passing** (offline).

New tests added:
- `test_industry_strength_basic` — verifies 20-day ROC matches manual calculation
- `test_industry_strength_no_etf_returns_none` — None industry_key → all-None dict
- `test_industry_strength_insufficient_bars_returns_none` — < 21 bars → mom is None, etf set
- `test_industry_above_50ma_flag` — uptrend True, downtrend False
- `test_industry_rs_spy_ratio` — ratio matches etf_mom/spy_mom via pytest.approx
- `test_industry_momentum_null_round_trip` — industry_momentum=None round-trips as SQL NULL
- `test_migrate_idempotent` — updated 8→9
- `test_migrate_schema_version_present` — updated 8→9
- `test_migrate_v1_to_current` — updated 8→9, added industry_* column assertions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_DDL` lacked new columns causing fresh-DB test failures**
- **Found during:** Task 2 (GREEN verify)
- **Issue:** `migrate()` runs `executescript(_DDL)` which creates the `signals` table. New columns only existed in the `ALTER TABLE` migration block, not in `_DDL`. Fresh-DB tests (used by every test fixture) got "table signals has no column named industry_group".
- **Fix:** Added all 4 new columns to the `_DDL` `CREATE TABLE` statement for `signals`.
- **Files modified:** `scanner/store_db.py`
- **Commit:** `116faef`

**2. [Rule 1 - Bug] `test_migrate_v1_to_current` asserted `== 8` (broken by schema bump)**
- **Found during:** Task 2 (GREEN verify)
- **Issue:** Pre-existing test builds a v1 DB and expects it to migrate to v8. After `_SCHEMA_VERSION = 9`, this fails with `assert 9 == 8`.
- **Fix:** Updated assertion to `== 9` and added assertions for the 4 new columns.
- **Files modified:** `tests/test_store_db.py`
- **Commit:** `116faef`

**3. [Rule 2 - Missing critical functionality] `if current < 8:` block lacked `current = 8` guard**
- **Found during:** Task 2 code review against the existing migration pattern
- **Issue:** The existing `if current < 8:` block in `migrate()` did not set `current = 8` after completing. This prevented the new `if current < 9:` block from running on a v7 DB upgrading directly to v9 in a single call.
- **Fix:** Added `current = 8` after the v8 migration block.
- **Files modified:** `scanner/store_db.py`
- **Commit:** `116faef`

## Known Stubs

None. `industry_rank_pct` column is intentionally unset in Plan 01 — Plan 02 populates it in a post-loop step. The column is NULL for all rows from this plan, which is expected and documented.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. Industry fields flow through parameterized `:named` placeholders only (T-02-03 disposition: mitigated). `industry_key` is used as a Python dict key only, never SQL-interpolated (T-02-01: mitigated). All arithmetic guards against `len < 21` before division and coerces NaN to `None` before insert (T-02-02: mitigated).

## Human Verification Required

A network-dependent check is needed after running a live scan to confirm:

1. `SELECT version FROM schema_version` → 9
2. `SELECT ticker, industry_group, industry_momentum, industry_above_50ma FROM signals ORDER BY created_at DESC LIMIT 10` — mapped tickers show non-null `industry_group` and signed `industry_momentum`; unmapped tickers show `NULL` (not `0.0`) in `industry_momentum`

Steps: `python scan.py refresh --file universes/sample.txt` then `python scan.py scan --strategy pullback --file universes/sample.txt`

## Self-Check: PASSED

- scanner/core.py: FOUND
- scanner/store_db.py: FOUND
- scanner/journal.py: FOUND
- tests/test_core.py: FOUND
- tests/test_store_db.py: FOUND
- commit 93a8d98 (RED tests): FOUND
- commit 116faef (GREEN implementation): FOUND
- commit 0f3b131 (live-scan wiring): FOUND
