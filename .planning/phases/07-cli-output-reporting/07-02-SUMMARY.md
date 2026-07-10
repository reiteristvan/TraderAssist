---
phase: 07-cli-output-reporting
plan: 02
subsystem: cli
tags: [pandas, seasonality, reporting, csv, cli]

# Dependency graph
requires:
  - phase: 07-cli-output-reporting (Plan 01)
    provides: pad_weeks_table, render_weeks_table, build_summary, write_weeks_csv, _SURVIVORSHIP_WARNING, _MULTIPLE_COMPARISON_CAVEAT in scanner/seasonality.py
provides:
  - "seasonality_by_week.py::main prints the survivorship-bias warning header, the 52-row per-week table, and the interpretive summary on every run (SEAS-10, SEAS-11, SEAS-12)"
  - "seasonality_by_week.py::main writes the padded table to CSV via --output, additive to stdout (D-14, SEAS-13)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single pad_weeks_table() call feeds both render_weeks_table (stdout) and write_weeks_csv (--output) from one local `padded` variable, guaranteeing stdout/CSV agreement (D-12) — same idiom scan.py uses for its --csv/--out pair"
    - "--output stays additive: stdout prints unconditionally, CSV write is a conditional side-effect gated on `if args.output`, never a replacement path (D-14)"

key-files:
  created: []
  modified:
    - seasonality_by_week.py
    - tests/test_seasonality_cli.py

key-decisions:
  - "Removed the Phase 6 placeholder 'Baseline:'/'Significant weeks:' print lines entirely — build_summary(result) now covers that content (baseline mean, significant-weeks list) with more explanatory text, per plan Task 1 instruction"
  - "Kept 'Bootstrap iters:'/'Seed:'/'Years:' as a standalone data-readiness line above the warning header — distinct from build_summary's interpretive content, mirrors the existing Sector/Admitted/Skipped context lines"
  - "Task 2's tdd=\"true\" tag did not produce a strict RED-then-GREEN commit pair: Task 1 already wired the full implementation, so Task 2's tests exercise already-working behavior (confirmatory/regression tests for the wiring), not a failing-first cycle driving new production code. Committed as a single test(...) commit, matching the plan's own Task 1 (implementation) / Task 2 (tests) split rather than forcing an artificial interleaving."

requirements-completed: [SEAS-10, SEAS-11, SEAS-12, SEAS-13]

coverage:
  - id: D1
    description: "main prints the survivorship-bias warning header before the table on every run"
    requirement: "SEAS-12"
    verification:
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_prints_survivorship_warning_header"
        status: pass
    human_judgment: false
  - id: D2
    description: "main prints the padded 52-row, 9-column table via pad_weeks_table + render_weeks_table, including N/A cells for weeks absent from the fake result"
    requirement: "SEAS-10"
    verification:
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_prints_padded_52_row_table"
        status: pass
    human_judgment: false
  - id: D3
    description: "main prints build_summary's interpretive content (significant-weeks list or none-message, plus the multiple-comparison caveat) on every run"
    requirement: "SEAS-11"
    verification:
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_prints_interpretive_summary"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_happy_path_prints_summary"
        status: pass
    human_judgment: false
  - id: D4
    description: "--output writes a 52-row, 9-column CSV (reusing the same padded DataFrame as stdout) while stdout still prints the full table/summary output (additive, not a replacement)"
    requirement: "SEAS-13"
    verification:
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_output_writes_csv_and_still_prints_stdout"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_without_output_writes_no_file"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality_cli.py#test_main_output_creates_missing_parent_dir"
        status: pass
    human_judgment: false

duration: ~10min
completed: 2026-07-10
status: complete
---

# Phase 7 Plan 2: Wire Presentation Functions Into the CLI Summary

**Wired Plan 01's pad_weeks_table/render_weeks_table/build_summary/write_weeks_csv into seasonality_by_week.py::main — the CLI now prints the survivorship warning, the padded 52-row table, and the interpretive summary on every run, and writes the same padded table to CSV when --output is given.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `main` prints, in order, the data-readiness context (Sector/Admitted/Skipped), the bootstrap-iters/seed/years line, the static survivorship-bias warning header (SEAS-12), the padded 52-row table (SEAS-10), and the interpretive summary (SEAS-11)
- `pad_weeks_table(result)` is called exactly once into a local `padded` variable, feeding both `render_weeks_table` (stdout) and, conditionally, `write_weeks_csv` — guaranteeing stdout and CSV can never disagree (D-12)
- `--output` is now fully additive: stdout always prints regardless of `--output`, and passing `--output <path>` writes the same padded table to CSV plus a `Saved → {path}` confirmation line (D-14/SEAS-13)
- `--output` argparse help text updated from "consumed in a later phase; not used yet" to describe its Phase 7 CSV-write behavior
- Removed the Phase 6 placeholder `Baseline:`/`Significant weeks:` print lines — `build_summary` now covers that content with fuller explanatory text
- 6 new CLI tests added (survivorship header, padded 52-row table with N/A cells, interpretive summary, `--output` CSV write + stdout still printing, no-`--output` writes no file, missing parent dir auto-created) plus the existing happy-path test's assertion updated for the new summary content
- Full `pytest -q` suite: 319 passed (up from 313 after Plan 01)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire header + table + summary + CSV into main** — `2141c8b` (feat)
2. **Task 2: CLI tests for header/table/summary/CSV + full pytest green** — `297e287` (test)

_Note: Task 2 was tagged `tdd="true"` in the plan, but since Task 1 already implemented the full wiring, Task 2's tests are confirmatory/regression tests over already-working behavior rather than a RED-then-GREEN cycle driving new production code. See Key Decisions._

## Files Created/Modified
- `seasonality_by_week.py` — `main` now prints the survivorship-warning header, the padded table, and the interpretive summary unconditionally, and conditionally writes CSV via `write_weeks_csv` when `--output` is given; `--output` help text updated; module docstring updated to describe Phase 7 behavior
- `tests/test_seasonality_cli.py` — `_fake_result`'s `weeks` fixture extended with `insufficient_years` and only weeks 1-2 present (exercises 52-row padding + N/A cells); 6 new tests for SEAS-10..13 behavior; happy-path test's placeholder-line assertion updated

## Decisions Made
- See `key-decisions` in frontmatter above (placeholder-line removal, standalone bootstrap-iters/seed/years line placement, Task 2's non-strict-TDD commit structure)

## Deviations from Plan

None — plan executed exactly as written. All D-01 through D-14 decisions from 07-CONTEXT.md were honored via the Plan 01 functions; no architectural changes, no new dependencies, no scope changes.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Phase 7 (CLI Output & Reporting) is now complete. `seasonality_by_week.py` delivers SEAS-10 through SEAS-13 end-to-end: the survivorship-bias warning, the padded 52-row table, the interpretive summary, and CSV export via `--output`. All three phases of the v1.1 Weekly Seasonality Analyzer milestone (05: sector resolution & data input, 06: seasonality statistics & verification, 07: CLI output & reporting) are complete. `pytest -q` is green at 319 passed. This closes out the v1.1 milestone's planned phases.

---
*Phase: 07-cli-output-reporting*
*Completed: 2026-07-10*
