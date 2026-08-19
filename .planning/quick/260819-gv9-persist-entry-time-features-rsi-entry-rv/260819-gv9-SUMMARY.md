---
phase: quick-260819-gv9
plan: 1
subsystem: database
tags: [sqlite, backtest, signals, winner-loser-analysis]

requires: []
provides:
  - "rsi_entry, rvol, pullback_depth_pct, pct_to_52w_high REAL columns on signals (schema v10)"
  - "entry_features() shared normalization helper in scanner/core.py"
  - "Both write paths (live scan, backtest ingest) populate the four columns"
affects: [report.py winner-loser analysis, future backtest re-runs]

tech-stack:
  added: []
  patterns:
    - "Single shared normalization helper called by both write paths (D-01), same pattern as _industry_strength"
    - "Helper returns None never NaN; journal-boundary coercion (_coerce_numeric) as a defense-in-depth backstop for the pandas NaN round-trip"

key-files:
  created: []
  modified:
    - scanner/core.py
    - scanner/backtest.py
    - scanner/store_db.py
    - scanner/journal.py
    - tests/test_core.py
    - tests/test_store_db.py
    - tests/test_journal.py

key-decisions:
  - "pct_to_52w_high stored as percent distance BELOW the 52-week high for both strategies and sources (D-03); BreakoutResult's native closeness value (99.51) is converted via 100.0 - raw to 0.49"
  - "entry_features() lives in scanner/core.py with a lazy BreakoutResult import inside the function body to avoid inverting the core -> strategies dependency"
  - "Namespaced entry_* keys in run_scan's row dict (entry_rsi, entry_rvol, entry_pullback_depth_pct, entry_pct_to_52w_high) to avoid colliding with asdict(result)'s existing pct_to_52w_high/pullback_depth_pct keys, which flow raw into combined.to_csv()"

requirements-completed: [ENTRY-FEAT-01]

coverage:
  - id: D1
    description: "signals table has four new REAL columns (rsi_entry, rvol, pullback_depth_pct, pct_to_52w_high) at schema_version 10, added additively"
    requirement: "ENTRY-FEAT-01"
    verification:
      - kind: unit
        ref: "tests/test_store_db.py::test_signals_table_has_v10_columns"
        status: pass
      - kind: unit
        ref: "tests/test_store_db.py::test_migrate_v9_to_v10_idempotent_preserves_existing_row"
        status: pass
    human_judgment: false
  - id: D2
    description: "Both insert_signal() and insert_signals_batch() carry the four columns independently"
    requirement: "ENTRY-FEAT-01"
    verification:
      - kind: unit
        ref: "tests/test_store_db.py::test_insert_signal_round_trips_entry_features"
        status: pass
      - kind: unit
        ref: "tests/test_store_db.py::test_insert_signals_batch_round_trips_entry_features"
        status: pass
    human_judgment: false
  - id: D3
    description: "entry_features() shared helper produces the four values for both strategies; pct_to_52w_high conversion (99.51 -> 0.49) pinned"
    requirement: "ENTRY-FEAT-01"
    verification:
      - kind: unit
        ref: "tests/test_core.py::test_entry_features_breakout_basic"
        status: pass
      - kind: unit
        ref: "tests/test_core.py::test_entry_features_legacy_equivalence_breakout"
        status: pass
      - kind: unit
        ref: "tests/test_core.py::test_entry_features_legacy_equivalence_pullback"
        status: pass
    human_judgment: false
  - id: D4
    description: "Live scan path (write_live_signals) and backtest ingest path (write_backtest_to_db) both write non-NULL entry-time columns via a DB round-trip"
    requirement: "ENTRY-FEAT-01"
    verification:
      - kind: unit
        ref: "tests/test_journal.py::test_write_live_signals_pullback_all_four_columns_non_null"
        status: pass
      - kind: unit
        ref: "tests/test_journal.py::test_write_live_signals_breakout_pullback_depth_null_pct_high_distance"
        status: pass
      - kind: unit
        ref: "tests/test_journal.py::test_write_backtest_to_db_signal_entry_features_round_trip"
        status: pass
    human_judgment: false
  - id: D5
    description: "Backtest inner loop keeps its precomputed .asof() fast path; no rolling(50)/rolling(252) recomputation introduced"
    requirement: "ENTRY-FEAT-01"
    verification:
      - kind: unit
        ref: "static inspect.getsource(generate_signals) check for 'entry_features', absence of '100.0 -'/'rolling(252'/'rolling(50', presence of 'asof'"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-08-19
status: complete
---

# Quick Task 260819-gv9: Persist entry-time signal features to signals table Summary

**Added rsi_entry/rvol/pullback_depth_pct/pct_to_52w_high as REAL columns (schema v10) written by both the live scan and backtest ingest paths through one shared `entry_features()` normalization helper — unblocking the winner/loser analysis that previously had no data for these four fields.**

## Performance

- **Duration:** ~4 min (task-commit span 12:35:58 - 12:39:15)
- **Started:** 2026-08-19T12:35:58+02:00
- **Completed:** 2026-08-19T12:39:15+02:00
- **Tasks:** 4 (3 code tasks + 1 verification-only task)
- **Files modified:** 7

## Accomplishments
- `entry_features(result, df, vol_sma50=None, high_52w=None)` added to `scanner/core.py` — a single, total (never-raising) helper producing all four entry-time metrics for both `PullbackResult` and `BreakoutResult`, pinned against a literal reimplementation of the pre-refactor `backtest.py:435-457` block.
- Schema bumped 9 -> 10: four `REAL` columns added additively to `signals` (`CREATE TABLE IF NOT EXISTS` DDL for fresh DBs, `ALTER TABLE` migration step for existing DBs); both `insert_signal()` and `insert_signals_batch()` wired independently.
- `backtest.py`'s `generate_signals()` inline normalization block (lines 435-458) replaced by a single `entry_features(...)` call, passing the precomputed `.asof()` scalars — no behavior change, no performance regression.
- `core.py`'s `run_scan()` calls `entry_features(result, df)` and assigns four namespaced `entry_*` keys, avoiding the `asdict(result)` key collision that would have silently inverted the breakout `pct_to_52w_high` value flowing into `combined.to_csv()`.
- `journal.py`'s `write_live_signals()` and `write_backtest_to_db()` both map the four DB-named columns through a new `_coerce_numeric()` boundary helper (None/NaN -> None, finite float otherwise).

## Task Commits

Each task was committed atomically:

1. **Task 1: Shared entry_features() helper in core.py, pinned against the legacy inline block** - `4260e35` (feat)
2. **Task 2: Schema v10 in store_db.py — four columns, both insert functions, idempotent migration** - `893b976` (feat)
3. **Task 3: Wire both write paths through the shared helper and prove neither writes NULL** - `ae81458` (feat)
4. **Task 4: Full-suite green, web-layer finding asserted, no-regression checks** - no code changes (all checks passed; nothing to commit)

_No TDD multi-commit tasks in this plan — Task 1 was `tdd="true"` but tests were authored alongside the helper in a single commit per this project's existing test/impl co-location convention seen in `tests/test_core.py`._

## Files Created/Modified
- `scanner/core.py` — `_safe_float()` and `entry_features()` helper (placed after `_attach_industry_rank_pct`); `run_scan()` now assigns four namespaced `entry_*` row keys
- `scanner/backtest.py` — `generate_signals()`'s inline normalization block replaced by an `entry_features()` call; removed the now-unused local `BreakoutResult` import
- `scanner/store_db.py` — `_SCHEMA_VERSION = 10`; four new `REAL` columns in the DDL and the v10 migration step; both insert functions updated
- `scanner/journal.py` — `_coerce_numeric()` boundary helper; `write_live_signals()` and `write_backtest_to_db()` map the four columns
- `tests/test_core.py` — 17 new tests for `entry_features()` (basic cases, degenerate denominators, fallback-vs-explicit equivalence, legacy-equivalence pins)
- `tests/test_store_db.py` — schema-version assertions bumped 9->10; 7 new tests for the v10 columns, both insert paths, and the simulated v9->v10 upgrade
- `tests/test_journal.py` — 4 new tests for live/backtest round-trips including the D-03 conversion and the NaN-to-NULL guarantee

## Decisions Made
- `entry_features()` distinguishes "caller passed `None`" (fall back to computing from the frame) from "caller passed a degenerate value" (`0.0`, negative, or `NaN` — trust the caller's answer and return `None`, no fallback). This matters for the backtest's `.asof()` scalars, which can legitimately be `NaN` early in a ticker's history (insufficient bars for the rolling window) — in that case falling back to a frame-level recompute would silently reintroduce the O(n) cost the precomputed series exists to avoid.
- Kept the journal-boundary `_coerce_numeric()` even though `entry_features()` never returns NaN, because NaN can still arrive at `write_live_signals()` via the `pandas.concat().to_dict("records")` round-trip in `scan.py` (prior_investigation 5) — this is a distinct source, not overlap with the helper's contract.

## Deviations from Plan

None - plan executed exactly as written.

One note, not a deviation: the plan's Task 1 `<verify>` automated command includes `! grep -nE 'datetime\.now|Timestamp\.now' scanner/core.py` over the *whole file*. This grep matches a pre-existing docstring line in `_industry_strength` ("...does NOT call datetime.now...") that predates this task (confirmed via `git show HEAD:scanner/core.py` before any change in this task). No wall-clock call was introduced by `entry_features()` itself — confirmed by grepping only the diff's added lines, which is empty for `datetime.now`/`Timestamp.now`. This is a known false-positive in the literal verify command, not a real regression; documented here per Task 4's "treat any failure as evidence... enumerate it... never rewrite it silently" instruction (though this is a pre-existing string match, not a test failure).

## Issues Encountered

None.

## Web-layer finding

**No web change required.** Verified by command, not assumed:
- `grep -rn "rsi_entry\|pullback_depth_pct\|pct_to_52w_high" web/api web/ui/src --include=*.js --include=*.ts` returns no matches — nothing under the web layer references the four new column names.
- `web/api/db/index.js`'s `_applyMigrations` remains guarded on `cols.includes('notes')` (line 71), so it stays a no-op against a v10 DB (which always has the `notes` column from schema v6) and cannot write `schema_version` backwards.
- `web/api/node_modules` was present, so `npm test` was run: **71/71 passed** (6 suites: signals, health, stats, runs, jobs, ohlcv). The Express layer's `SELECT *` queries pass the four new columns straight through as extra JSON keys with no schema break.

## Migration evidence

Ran `migrate()` twice against a **temp-directory copy** of the real `data/scanner.db` (never the original):
- Before: 192,217 `source='backtest'` rows, 102 `source='live'` rows (matches the counts recorded during planning).
- After two `migrate()` calls: same 192,217 backtest rows, same 102 live rows, `schema_version` = 10, all four new columns present, and `SELECT COUNT(*) FROM signals WHERE rsi_entry IS NOT NULL OR rvol IS NOT NULL OR pullback_depth_pct IS NOT NULL OR pct_to_52w_high IS NOT NULL` = 0 (zero pre-existing rows backfilled).
- The real `data/scanner.db` on disk is **still schema v9** — confirmed via `SELECT version FROM schema_version` against the actual file after this task completed, and `git status` shows `data/scanner.db` in the same pre-existing modified state it was found in (unrelated prior working-tree change, left untouched). It will pick up v10 automatically the next time `scan.py scan`, `scan.py refresh`, or `scan.py backtest` runs.

## Changed Expectations

None. `pytest -q` was 358/358 passing both before assertion and after all three code tasks — no existing test's expected value moved. Two schema-version literal assertions (`== 9` -> `== 10`) in `tests/test_store_db.py` were updated as *part of* Task 2's own test additions (not a side effect discovered afterward), consistent with the plan's explicit instruction to extend that file's version assertions for the v10 bump.

## Circular-import finding

Confirmed safe. `entry_features()` lives in `scanner/core.py` and imports `BreakoutResult` lazily inside the function body (`from scanner.strategies.breakout import BreakoutResult`), matching the existing pattern already used at `core.py` (in `run_scan`) and `backtest.py`. `core.py`'s module-level imports remain stdlib + `pandas` + `yfinance` only — no import cycle was introduced. Verified empirically: `python -c "import scanner.core, scanner.backtest, scanner.journal"` succeeds, and the full test suite (358 tests across all modules) imports and runs cleanly.

## Follow-up

The four columns are `NULL` for all 192,217 + 102 pre-existing rows. Populating them requires a fresh backtest run (out of scope for this task — a separate follow-up, ~2.9h for 3 years on sp600 per the CONTEXT.md estimate) or waiting for new live scans to accumulate. The winner/loser analysis over run `4f4fe68_2021-01-01_20260702_090418` will need a re-run before these fields become queryable for that historical dataset.

## Next Phase Readiness

Persistence is unblocked. `report.py` already consumes these four fields in-memory (unchanged by this task per D-04's persistence-only scope) — no further engine work is needed before a fresh backtest run makes the columns queryable for winner/loser discriminant analysis.

---
*Phase: quick-260819-gv9*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 7 code/test files and the SUMMARY itself verified present on disk; all 3 task commits (`4260e35`, `893b976`, `ae81458`) verified present in `git log --oneline --all`.
