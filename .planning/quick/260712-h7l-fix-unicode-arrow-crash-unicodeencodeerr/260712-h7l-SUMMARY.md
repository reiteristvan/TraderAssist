---
phase: quick-260712-h7l
plan: 1
subsystem: cli
tags: [encoding, cli, pytest, subprocess, windows]

requires:
  - phase: 07-cli-output-reporting
    provides: seasonality_by_week.py --output CSV export, scan.py --csv export
provides:
  - ASCII-safe "Saved -> {path}" confirmation prints in seasonality_by_week.py and scan.py
  - Subprocess-based regression test exercising a real cp1252-encoded stream
affects: [07-cli-output-reporting]

tech-stack:
  added: []
  patterns:
    - "Regression tests for stream-encoding bugs must use subprocess + PYTHONIOENCODING, not capsys (capsys bypasses real stream encoding)"

key-files:
  created:
    - tests/_regression_cp1252_helper.py
  modified:
    - seasonality_by_week.py
    - scan.py
    - tests/test_seasonality_cli.py

key-decisions:
  - "Replaced U+2192 arrow with ASCII '->' rather than wrapping print in a try/except or forcing UTF-8 reconfiguration, since the plan scoped this narrowly to the unencodable character itself"
  - "Fixed the identical bug in scan.py's --csv confirmation print even though scan.py is outside Phase 7, per the plan's explicit scope note (pre-existing sibling occurrence of the same bug)"

patterns-established:
  - "Stream-encoding regression tests: use subprocess.run with PYTHONIOENCODING set explicitly and a standalone `_`-prefixed helper script (excluded from pytest discovery) rather than trying to reconfigure sys.stdout.encoding in-process"

requirements-completed: [SEAS-13]

coverage:
  - id: D1
    description: "seasonality_by_week.py --output confirmation print no longer crashes with UnicodeEncodeError on cp1252 streams"
    requirement: "SEAS-13"
    verification:
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_output_writes_csv_and_still_prints_stdout"
        status: pass
      - kind: integration
        ref: "tests/test_seasonality_cli.py#test_main_output_survives_cp1252_stream_encoding"
        status: pass
    human_judgment: false
  - id: D2
    description: "scan.py --csv confirmation print fixed with the identical ASCII replacement"
    verification:
      - kind: unit
        ref: "grep -c \"Saved -> \" scan.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Full pytest suite (320 tests) stays green after both fixes"
    verification:
      - kind: unit
        ref: "pytest -q"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-07-12
status: complete
---

# Quick Task 260712-h7l: Fix Unicode Arrow Crash Summary

**Replaced the U+2192 right-arrow in two CSV confirmation prints with ASCII "->" so the CLI no longer crashes with UnicodeEncodeError on cp1252-encoded Windows streams, and added a subprocess-based regression test that exercises a real (non-capsys) stream encoding.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2 completed
- **Files modified:** 4 (2 created/modified in Task 1's test, 1 new helper in Task 2)

## Accomplishments
- `seasonality_by_week.py`'s `--output` confirmation print and `scan.py`'s `--csv` confirmation print now use ASCII-only text, closing the crash documented in 07-VERIFICATION.md
- Added `tests/_regression_cp1252_helper.py`, a standalone (non-collected) subprocess helper that runs the real `seasonality_by_week.py` CLI path end to end with fake load/compute functions
- Added `test_main_output_survives_cp1252_stream_encoding`, which forces `PYTHONIOENCODING=cp1252` via `subprocess.run` and asserts a clean exit — closing the coverage gap where `capsys` (an in-memory buffer) can never reproduce a real stream-encoding crash
- Full `pytest -q` suite stays green: 320 passed

## Task Commits

1. **Task 1: Replace the unencodable arrow character in both confirmation prints** - `ca719f7` (fix)
2. **Task 2: Add a subprocess-based regression test for real stream encoding** - `3693475` (test)

**Plan metadata:** `03e12da` (pre-dispatch commit), merged via `8661496`

## Files Created/Modified
- `seasonality_by_week.py` - Line 102 confirmation print changed to `Saved -> {path}` (ASCII)
- `scan.py` - Line 160 confirmation print changed to `Saved -> {path}` (ASCII); pre-existing sibling occurrence of the same bug, fixed per plan scope
- `tests/test_seasonality_cli.py` - Updated stale arrow assertion in `test_main_output_writes_csv_and_still_prints_stdout`; added `test_main_output_survives_cp1252_stream_encoding` plus its `os`/`subprocess`/`sys`/`Path` imports
- `tests/_regression_cp1252_helper.py` (new) - Standalone subprocess helper that runs `seasonality_by_week.py`'s CLI `main()` with fake `load_sector_dataset`/`compute_seasonality_stats` reassigned at the module level, writing a CSV and exercising the confirmation print through a real OS-level stream

## Decisions Made
- Chose the plan's specified ASCII "->" replacement over alternative fixes (e.g., forcing UTF-8 stdout reconfiguration) since it is the minimal, narrowly-scoped fix the plan called for and avoids touching stream-encoding configuration elsewhere in the CLI
- Confirmed via direct byte inspection that no U+2192 character remains in either changed print line (manual verification step from the plan's `<verification>` block)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Phase 7's SEAS-13 gap identified in 07-VERIFICATION.md is closed: `--output` now writes the CSV AND the process exits cleanly (verified both via the existing capsys-based test and the new subprocess-based cp1252 regression test). No blockers for further Phase 7 work.

---
*Phase: quick-260712-h7l*
*Completed: 2026-07-12*

## Self-Check: PASSED

All created/modified files found on disk; both task commits (`ca719f7`, `3693475`) found in git log.
