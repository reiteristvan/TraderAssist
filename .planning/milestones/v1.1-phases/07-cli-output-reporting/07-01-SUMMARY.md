---
phase: 07-cli-output-reporting
plan: 01
subsystem: cli
tags: [pandas, seasonality, reporting, csv]

# Dependency graph
requires:
  - phase: 06-seasonality-statistics-verification
    provides: SeasonalityResult dataclass, compute_seasonality_stats, the 11-column weeks DataFrame (mean/delta/CI/median/n_obs/n_years/significant/insufficient_years/std_bps)
provides:
  - "pad_weeks_table(result) — 52-row, 9-column SEAS-10 display DataFrame with N/A padding for missing/insufficient_years weeks"
  - "render_weeks_table(padded) — plain-text stdout rendering via to_string(index=False)"
  - "build_summary(result) — interpretive summary text: baseline, significant-weeks list, top-5/bottom-5, insufficient_years callout, multiple-comparison caveat"
  - "write_weeks_csv(padded, path) — CSV export of the same padded table, auto-creating parent dirs"
  - "_SURVIVORSHIP_WARNING and _MULTIPLE_COMPARISON_CAVEAT static text constants"
affects: [07-cli-output-reporting Plan 02 (seasonality_by_week.py CLI wiring)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared-padded-DataFrame idiom: one pad_weeks_table() call feeds both render_weeks_table (stdout) and write_weeks_csv (file), guaranteeing the two outputs never disagree (D-12)"
    - "N/A sentinel formatting guarded by explicit pd.isna checks, never bare truthy tests, per the codebase's bool(NaN)-is-True pitfall"
    - "accumulate lines, join once" text-assembly idiom (mirrors report.py::render_report)
    - "_-prefixed static string constants for fixed warning/caveat text (mirrors report.py::_BIAS_SURVIVORSHIP)"

key-files:
  created: []
  modified:
    - scanner/seasonality.py
    - tests/test_seasonality.py

key-decisions:
  - "pad_weeks_table drops insufficient_years and std_bps from its output — they are Phase 6 internals, not SEAS-10 display columns (D-02, D-11); insufficient_years is communicated via N/A CI cells plus build_summary's explicit callout instead"
  - "Top-5/bottom-5-by-delta dedup strategy: highest gets priority (first min(5, available) weeks by descending delta), lowest gets whatever distinct weeks remain after excluding highest — satisfies D-08's 'no double-counting' requirement without forcing exactly 5+5 on thin datasets"
  - "Two test assertions changed from 'is False' to 'bool(...) is False' — a pandas bool-dtype column always returns np.bool_ scalars on element access regardless of the Python bool used at construction time; this is a pandas quirk, not an implementation bug"
  - "write_weeks_csv lets a genuinely unwritable path's OSError propagate uncaught (no try/except) — D-13's auto-create/overwrite choice makes this an unexpected-path case, not a routine one, so no new ValueError wrapping was added speculatively"

requirements-completed: [SEAS-10, SEAS-11, SEAS-12, SEAS-13]

coverage:
  - id: D1
    description: "pad_weeks_table pads SeasonalityResult.weeks to a fixed 52-row, 9-column display DataFrame; missing weeks get N/A + significant=False, insufficient_years weeks blank only the CI columns, and 5 bps columns render to exactly 2 decimals"
    requirement: "SEAS-10"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_pad_weeks_table_returns_52_rows_ascending_with_9_columns"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_pad_weeks_table_missing_week_is_na_and_not_significant"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_pad_weeks_table_insufficient_years_blanks_ci_only"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_pad_weeks_table_bps_columns_formatted_to_two_decimals"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_pad_weeks_table_no_insufficient_years_or_std_bps_columns"
        status: pass
    human_judgment: false
  - id: D2
    description: "render_weeks_table renders the padded table as plain text via DataFrame.to_string(index=False), containing all 9 headers, 52 data lines, and the N/A sentinel"
    requirement: "SEAS-10"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_render_weeks_table_contains_headers_and_52_rows_and_na_sentinel"
        status: pass
    human_judgment: false
  - id: D3
    description: "build_summary assembles interpretive text: baseline mean, significant-weeks list (week+delta+CI) or the explicit none-message, always-present top-5/bottom-5 by delta deduplicated on thin data, an insufficient_years uncomputable-CI callout, and the multiple-comparison caveat"
    requirement: "SEAS-11"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_build_summary_lists_significant_weeks_with_week_delta_ci"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_build_summary_zero_significant_weeks_shows_none_message"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_build_summary_top5_bottom5_always_present_and_deduped_when_thin"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_build_summary_includes_baseline_and_caveat"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_build_summary_insufficient_years_callout"
        status: pass
    human_judgment: false
  - id: D4
    description: "_SURVIVORSHIP_WARNING and _MULTIPLE_COMPARISON_CAVEAT module-level constants: static, non-interpolated, mechanism-explaining text"
    requirement: "SEAS-12"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_survivorship_warning_constant_content"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_survivorship_warning_constant_is_fixed_every_call"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_multiple_comparison_caveat_constant_content"
        status: pass
    human_judgment: false
  - id: D5
    description: "write_weeks_csv writes the same padded 52-row table to CSV, auto-creating parent directories and overwriting an existing target silently"
    requirement: "SEAS-13"
    verification:
      - kind: unit
        ref: "tests/test_seasonality.py#test_write_weeks_csv_creates_missing_parent_dirs"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_write_weeks_csv_52_rows_9_columns_no_insufficient_years"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_write_weeks_csv_content_matches_padded_including_na"
        status: pass
      - kind: unit
        ref: "tests/test_seasonality.py#test_write_weeks_csv_overwrites_existing_file_silently"
        status: pass
    human_judgment: false

duration: ~5min
completed: 2026-07-10
status: complete
---

# Phase 7 Plan 1: Seasonality Presentation Functions Summary

**Added pad_weeks_table, render_weeks_table, build_summary, and write_weeks_csv to scanner/seasonality.py — the padded-52-week table, interpretive summary text, and CSV export that turn Phase 6's raw SeasonalityResult into readable output.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-07-10T16:01:01+02:00
- **Completed:** 2026-07-10T16:05:06+02:00
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- `pad_weeks_table(result)` reindexes `SeasonalityResult.weeks` onto the full ISO week range 1..52, honoring the N/A-padding rules for absent weeks (D-01) and `insufficient_years` weeks (D-02), formatting the 5 bps columns to exactly 2 decimals (D-03), and emitting exactly the 9 SEAS-10 display columns in order (D-11)
- `render_weeks_table(padded)` renders the padded table as plain text via `DataFrame.to_string(index=False)` (D-04) — no new dependency
- `build_summary(result)` assembles the interpretive summary: baseline mean, significant-weeks list (or the explicit none-message), always-present top-5/bottom-5 by delta with dedup on thin datasets, an explicit "uncomputable CI" callout for `insufficient_years` weeks, and the multiple-comparison caveat text
- `write_weeks_csv(padded, path)` writes the SAME padded DataFrame to CSV, auto-creating parent directories and overwriting silently — guarantees stdout and CSV never disagree (D-12)
- Two static module constants (`_SURVIVORSHIP_WARNING`, `_MULTIPLE_COMPARISON_CAVEAT`) hold the mechanism-explaining, non-interpolated warning/caveat text per the "loud and honest" theme
- 24 new unit tests added to `tests/test_seasonality.py` (full project suite: 313 passing, up from 295)

## Task Commits

Each task was committed atomically (TDD RED/GREEN pairs):

1. **Task 1: pad_weeks_table + render_weeks_table** — `e986896` (test), `c121aef` (feat)
2. **Task 2: build_summary + warning/caveat constants** — `112abc7` (test), `e9b363c` (feat)
3. **Task 3: write_weeks_csv** — `e7f4dd7` (test), `fc66b5c` (feat)

_Note: all three tasks used the RED/GREEN TDD cycle — a failing test commit followed by the implementing feat commit. No refactor commits were needed._

## Files Created/Modified
- `scanner/seasonality.py` — added `pad_weeks_table`, `render_weeks_table`, `build_summary`, `write_weeks_csv`, `_DISPLAY_COLUMNS`/`_BPS_COLUMNS`/`_NA` helpers, and the `_SURVIVORSHIP_WARNING`/`_MULTIPLE_COMPARISON_CAVEAT` constants
- `tests/test_seasonality.py` — added 24 unit tests covering all four new functions plus the two constants; added `Path` import and a shared `_make_result`/`_week_row` test-fixture pair

## Decisions Made
- Priority-based top/bottom dedup: highest gets first claim on `min(5, available)` weeks by descending delta; lowest takes whatever distinct weeks remain after excluding those already in highest — satisfies D-08's "no double-counting" without forcing exactly 5+5 on a thin dataset
- Two test assertions were corrected from `is False` to `bool(...) is False` after discovering a pandas quirk: a bool-dtype column always yields `np.bool_` scalars on element access, even when the Python bool literal `False` was used at DataFrame construction time. Not a code bug — a pre-existing convention already used elsewhere in this test file (e.g. `test_bootstrap_ci_week_never_drawn_flagged_insufficient_years`)
- `write_weeks_csv` does not wrap I/O errors in `ValueError` — D-13's auto-create/overwrite choice means an unwritable path is a genuinely unexpected condition, so the underlying `OSError` is left to propagate uncaught rather than adding speculative error-handling

## Deviations from Plan

None - plan executed exactly as written. All D-01 through D-13 decisions were implemented as specified in 07-CONTEXT.md; no architectural changes, no new dependencies, no scope changes.

## Issues Encountered
- One test-only correction (`pd.read_csv`'s default NA-value parsing treats the literal `"N/A"` cell text as a missing-value sentinel and silently converts it back to `NaN`, even with `dtype=str`). Fixed by adding `keep_default_na=False` to the CSV-content read-back test. This is a test-harness detail, not a bug in `write_weeks_csv` — the CSV file on disk correctly contains the literal string `N/A`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

All four Phase 7 functions and the two static constants exist in `scanner/seasonality.py`, are pure/testable without argparse, and honor D-01 through D-13. `pytest -q` stays green (313 passed). Plan 02 can now wire `pad_weeks_table` → `render_weeks_table` → print, `build_summary` → print, and `write_weeks_csv` (guarded by `if args.output`) into `seasonality_by_week.py::main`, replacing its current placeholder summary print and activating the previously-unused `--output` flag.

---
*Phase: 07-cli-output-reporting*
*Completed: 2026-07-10*

## Self-Check: PASSED

All 7 commits (e986896, c121aef, 112abc7, e9b363c, e7f4dd7, fc66b5c, 085f930) verified present in git log. `scanner/seasonality.py` and `tests/test_seasonality.py` confirmed on disk.
