---
phase: 05-sector-resolution-data-input
plan: 03
subsystem: cli
tags: [argparse, cli, seasonality, thin-dispatcher]

# Dependency graph
requires:
  - "scanner/seasonality.py — load_sector_dataset, SectorDataset (from 05-02)"
provides:
  - "seasonality_by_week.py — repo-root CLI entry point (build_parser, main) for SEAS-01/SEAS-02"
affects: [06-weekly-seasonality-statistics, 07-cli-output-csv-export]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thin-CLI / logic-in-scanner-module convention (mirrors scan.py's cmd_refresh delegate-and-print shape, D-04)"
    - "CLI surface anticipates later phases: --output/--bootstrap-iters/--seed declared now, unused until Phase 6/7"

key-files:
  created:
    - seasonality_by_week.py
    - tests/test_seasonality_cli.py
  modified: []

key-decisions:
  - "main() prints 'Admitted: N  Skipped: N' as fixed-format labels (not just embedded counts) so both automated tests and human operators can grep the summary reliably"
  - "Skipped-ticker preview capped at first 10 pairs to keep output readable for large universes (e.g. sp_all ~1,500 tickers)"

requirements-completed: [SEAS-01, SEAS-02]

coverage:
  - id: D1
    description: "main(['--sector','Technology','--universe','sp500']) delegates to load_sector_dataset once and prints resolved sector + admitted/skipped counts, returns 0"
    requirement: "SEAS-01"
    verification:
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_happy_path_prints_summary"
        status: pass
    human_judgment: false
  - id: D2
    description: "An unknown --sector prints the ValueError's valid-sector-names message to stderr, returns 2, and never reaches history validation (get_history not called)"
    requirement: "SEAS-02"
    verification:
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_invalid_sector_exits_nonzero_no_analysis"
        status: pass
    human_judgment: false
  - id: D3
    description: "--universe defaults to sp500 when omitted"
    requirement: "SEAS-01"
    verification:
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_default_universe_is_sp500"
        status: pass
    human_judgment: false
  - id: D4
    description: "seasonality_by_week.py --help exits 0 and lists all six flags; file contains no yfinance import and no sector/history logic (delegation only)"
    requirement: "SEAS-01, SEAS-02"
    verification:
      - kind: manual
        ref: "python seasonality_by_week.py --help; grep -c 'import yfinance' seasonality_by_week.py"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-07-09
status: complete
---

# Phase 5 Plan 3: Thin CLI Entry Point Summary

**seasonality_by_week.py — a thin argparse CLI mirroring scan.py's delegate-and-print convention, wrapping scanner.seasonality.load_sector_dataset and printing a Phase-5 data-readiness summary; unknown sectors exit 2 with a valid-names listing before any analysis runs**

## Performance

- **Duration:** ~11 min
- **Started:** 2026-07-09T15:13:00Z
- **Completed:** 2026-07-09T15:24:28Z
- **Tasks:** 2 completed
- **Files modified:** 2 (both new)

## Accomplishments

- `seasonality_by_week.py` created at repo root: `build_parser()` defines `--sector` (required), `--universe` (default `sp500`), `--years` (optional int), and the Phase 6/7 placeholder flags `--output`, `--bootstrap-iters`, `--seed` (each with a help string noting they're consumed in a later phase)
- `main(argv=None)` configures `logging.basicConfig(level=logging.INFO)`, parses args, calls `scanner.seasonality.load_sector_dataset(args.sector, args.universe, years=args.years)` inside a `try/except ValueError`
- On success: prints `Sector: {ds.sector}  Universe: {ds.universe}` and `Admitted: {len(ds.frames)}  Skipped: {len(ds.skipped)}`, plus up to 10 `(ticker, reason)` skip pairs; returns 0
- On `ValueError` (unknown `--sector`): prints the exception's valid-sector-names message to stderr, returns 2 — SEAS-02's "clear error exit, no analysis" behavior, since `resolve_sector` inside `load_sector_dataset` raises before `load_universe_file`/`get_history` are ever called
- The file contains zero sector-matching or history-validation logic and zero `yfinance` imports — verified by `grep -c 'import yfinance'` returning 0 and manual inspection; all logic delegation runs through `scanner.seasonality.load_sector_dataset`
- `tests/test_seasonality_cli.py` created with 3 tests: happy-path summary content, invalid-sector non-zero exit with no downstream `get_history` call, and default-universe-is-sp500
- Full suite grew from 257 to 260 passing tests, all green offline

## Task Commits

Each task was committed atomically:

1. **Task 1: Create seasonality_by_week.py thin CLI** - `67ad322` (feat)
2. **Task 2: tests/test_seasonality_cli.py** - `26b3da0` (test)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `seasonality_by_week.py` - New repo-root CLI entry point: `build_parser()`, `main()`, thin delegate-and-print shape mirroring `scan.py`'s `cmd_refresh`
- `tests/test_seasonality_cli.py` - 3 tests covering the happy-path summary, SEAS-02's non-zero exit with no analysis, and the sp500 default universe

## Decisions Made

- Followed the plan's task order (implementation in Task 1, tests in Task 2) rather than a strict RED/GREEN split per task — consistent with how Plan 02 was structured; the plan itself organizes the work this way
- Chose a fixed-format `"Admitted: N  Skipped: N"` label pair in the summary print so tests can assert on stable substrings rather than parsing loosely-formatted prose
- Capped the skipped-ticker preview at 10 pairs to keep stdout readable for the `all` universe (~1,500 tickers) while still surfacing enough detail to diagnose why tickers were excluded

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched their `<action>`/`<verify>`/`<acceptance_criteria>` specs; no auto-fixes, no architectural changes, no auth gates.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `seasonality_by_week.py --sector <name> --universe <name> [--years N]` is a working end-to-end CLI for SEAS-01/SEAS-02, ready for real-world manual testing against `universes/sample.txt` or `sp500.txt`
- The `--output`, `--bootstrap-iters`, `--seed` flags are declared on the parser but intentionally unused — Phase 6 (statistics) and Phase 7 (CLI output/CSV export) wire them in
- `pytest -q` full suite (260 tests) green offline
- Phase 5 (sector-resolution-data-input) is now complete across all 3 plans: `sector_store.py` (05-01), `seasonality.py` pipeline (05-02), and this thin CLI (05-03)

---
*Phase: 05-sector-resolution-data-input*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: seasonality_by_week.py
- FOUND: tests/test_seasonality_cli.py
- FOUND commit: 67ad322
- FOUND commit: 26b3da0
