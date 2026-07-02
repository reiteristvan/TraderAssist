---
phase: 03-industry-display-in-cli-web-ui
plan: "01"
subsystem: cli
tags: [cli, display, industry-momentum, tdd]
status: complete

dependency_graph:
  requires: [02-02-SUMMARY.md]
  provides: [cli-industry-columns]
  affects: [scan.py, tests/test_scan_display.py]

tech_stack:
  added: []
  patterns:
    - "NULL-guard lambda: v is not None and not pd.isna(v) for mixed None/NaN column safety"
    - "Integer-equality check (== 1, == 0) to avoid falsy-zero misclassification for industry_above_50ma"
    - "in df.columns guard on each formatted column for backward-compatible _print_scan_results"

key_files:
  created:
    - tests/test_scan_display.py
  modified:
    - scan.py

decisions:
  - "Used in df.columns guard on each of the 4 formatted columns so _print_scan_results stays robust when called with frames that predate Phase 2 industry fields"
  - "Integer-equality check (== 1, not truthy) for industry_above_50ma — 0 is a valid below-50MA state"
  - "display_df is a full .copy() of qualified before any mutation — never mutates the caller's frame"

metrics:
  duration: "2m"
  completed: "2026-07-01"
  tasks_completed: 2
  files_changed: 2

requirements: [IND-07]
---

# Phase 03 Plan 01: CLI Industry Columns Summary

**One-liner:** CLI scan output now shows Industry group, signed momentum percent, 50MA trend arrow, and rank percentile between Conf and Entry columns with strict NULL-to-em-dash handling.

## What Was Built

Extended `_print_scan_results()` in `scan.py` to show four new industry momentum columns between `confidence` and `close` in the qualified-setups table:

| Column | Source field | Format | NULL |
|--------|-------------|--------|------|
| Industry | `industry_group` | stored string | `—` |
| Mom | `industry_momentum` | `+5.2%` / `-3.1%` | `—` |
| Trend | `industry_above_50ma` | `↑` (==1) / `↓` (==0) | `—` |
| Rank% | `industry_rank_pct` | `Top 18%` | `—` |

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Failing test for industry columns (RED) | 0100379 | tests/test_scan_display.py (+116) |
| 2 | Extend _print_scan_results (GREEN) | ac273f0 | scan.py (+45/-4) |

## Verification

- `python -m pytest tests/test_scan_display.py -x` — PASSED
- `python -m pytest -q` — 231 passed (full offline suite, no regressions)
- Column order confirmed: `grep -n "Industry" scan.py` shows `Industry` at line 198 in the `cols` list, between `confidence` and `close`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all four columns are wired to real source fields from the Phase 2 computation. The `in df.columns` guard falls back to `"—"` only when a source column is absent from the frame (e.g., legacy callers), not as a display stub.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes. Display-only formatting of already-computed values (T-03-01 and T-03-02 accepted at ASVS Level 1 per plan threat model).

## Self-Check: PASSED

- tests/test_scan_display.py exists: FOUND
- scan.py modified: FOUND
- Commit 0100379 exists: FOUND
- Commit ac273f0 exists: FOUND
