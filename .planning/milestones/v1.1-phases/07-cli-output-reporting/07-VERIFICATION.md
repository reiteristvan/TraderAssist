---
phase: 07-cli-output-reporting
verified: 2026-07-12T00:00:00Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/4
  gaps_closed:
    - "Passing --output <path> writes the results table to CSV, while stdout output still happens regardless (Success Criterion 4 / SEAS-13)"
  gaps_remaining: []
  regressions: []
---

# Phase 7: CLI Output & Reporting Verification Report

**Phase Goal:** Results are presented to the user as a readable per-week table, an interpretive summary with anti-overfitting caveats, and an optional CSV export.
**Verified:** 2026-07-12
**Status:** passed
**Re-verification:** Yes — prior gap fixed by quick task 260712-h7l

## Goal Achievement

### Observable Truths

| # | Truth (Roadmap Success Criteria) | Status | Evidence |
|---|-------|--------|----------|
| 1 | The CLI prints a 52-row table sorted by week with columns week, mean_daily_ret_bps, delta_vs_baseline_bps, ci_low_bps, ci_high_bps, median_bps, n_obs, n_years, significant | ✓ VERIFIED | Re-run for this verification pass, real non-mocked invocation (`python seasonality_by_week.py --sector Technology --universe sp500 --bootstrap-iters 200 --seed 1`) against cached OHLCV data — printed exactly 52 rows (weeks 1–52 ascending) with exactly these 9 headers |
| 2 | The CLI prints a summary showing the baseline mean, the significant weeks (or the explicit "none — no week deviates significantly from baseline" message), and the 5 highest/lowest weeks by delta with a multiple-comparison caveat | ✓ VERIFIED | Same real run printed `Baseline mean daily return across the full sample: 5.99 bps`, a 7-week significant list (`Week 7: 18.60 bps (CI: 4.67 to 35.55)` etc.), "Top 5 highest-delta weeks" / "Bottom 5 lowest-delta weeks" sections, and the full multiple-comparison caveat text (52 tests, ~5% significance, ~2-3 false positives expected by chance) |
| 3 | A one-line survivorship-bias warning appears in the output header | ✓ VERIFIED | Same real run printed the static `_SURVIVORSHIP_WARNING` constant as a single line, positioned before the table |
| 4 | Passing `--output <path>` writes the results table to CSV, while stdout output still happens regardless | ✓ VERIFIED (gap closed) | Re-ran the exact repro scenario from the prior verification pass: `python seasonality_by_week.py --sector Technology --universe sp500 --bootstrap-iters 200 --seed 1 --output <path>.csv`, real cached data (82 admitted tickers, 65 years). **Exit code 0** (previously exit 1). Confirmation line `Saved -> <path>` printed (ASCII `->`, no U+2192). No traceback, no `UnicodeEncodeError`. CSV file verified on disk: 53 lines (1 header + 52 data rows), 9 columns matching the stdout table exactly. `sys.stdout.encoding` confirmed `cp1252` on this machine — same platform condition that reproduced the original crash. |

**Score:** 4/4 truths verified

### Fix Verification (quick task 260712-h7l)

| Check | Result |
|-------|--------|
| `seasonality_by_week.py:102` confirmation print | `print(f"\nSaved -> {args.output}")` — ASCII `->`, no U+2192. Confirmed via byte-level scan of the file (no `→` character present). |
| `scan.py:160` confirmation print (sibling occurrence, same bug class, fixed per quick task's explicit scope) | `print(f"\nSaved -> {args.csv}")` — ASCII `->`, no U+2192. Note: `scan.py:116` contains an unrelated `→` character inside a **Python comment** (`# None → skip gate`) — comments are never written to stdout, so this does not reproduce the crash and is out of scope for this fix. |
| Real, non-mocked `--output` run against cached data | Exit 0, `Saved -> <path>` printed, CSV correct on disk (52 rows × 9 cols) — reproduced directly by this verifier, independent of the quick task's own tests |
| New regression test `tests/test_seasonality_cli.py::test_main_output_survives_cp1252_stream_encoding` | Exists, runs the real CLI (`seasonality_by_week.py::main`, not mocked at the print layer) as a subprocess with `PYTHONIOENCODING=cp1252` forced via `tests/_regression_cp1252_helper.py`, asserts `returncode == 0`, no `Traceback`, no `UnicodeEncodeError`, CSV exists, `"Saved"` in stdout. This closes the exact coverage gap the prior verification flagged (`capsys` is encoding-blind). Confirmed present in test file and passing in the full suite run below. |
| `python -m pytest -q` (full suite, run once by this verifier) | **320 passed**, 2 pre-existing RuntimeWarnings (unrelated to Phase 7 — `log()` of zero/negative close prices in `test_compute_log_returns_*`), 0 failures. Up from 319 at the prior verification pass (the one new regression test). |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scanner/seasonality.py` | `pad_weeks_table`, `render_weeks_table`, `build_summary`, `write_weeks_csv` + 2 static constants | ✓ VERIFIED | Unchanged since prior verification; re-confirmed working via the real end-to-end run above |
| `seasonality_by_week.py` | `main` wired to print header/table/summary and conditionally write CSV | ✓ VERIFIED | Wiring unchanged; the previously-defective confirmation print now uses ASCII text and completes without crashing |
| `tests/test_seasonality.py` | Unit tests for the 4 Phase 7 functions | ✓ VERIFIED | Unchanged, part of the 320-passing full suite |
| `tests/test_seasonality_cli.py` | CLI tests for header/table/summary/CSV wiring | ✓ VERIFIED | Existing `test_main_output_writes_csv_and_still_prints_stdout` assertion updated to match the ASCII confirmation text; new `test_main_output_survives_cp1252_stream_encoding` added — no longer blind to the crash class |
| `tests/_regression_cp1252_helper.py` (new) | Standalone subprocess helper exercising the real CLI path under a forced cp1252 stream | ✓ VERIFIED | Present on disk, not collected by pytest (excluded by the `_`-prefix naming convention), invoked directly via `subprocess.run` from the new regression test |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `seasonality_by_week.py::main` | `pad_weeks_table(result)` | single call into local `padded` | ✓ WIRED | `seasonality_by_week.py:95` |
| `padded` | `render_weeks_table(padded)` (stdout) | direct call | ✓ WIRED | `seasonality_by_week.py:96` |
| `padded` | `write_weeks_csv(padded, args.output)` (CSV) | direct call, same `padded` instance | ✓ WIRED | `seasonality_by_week.py:101` — CSV-on-disk content matched the printed table exactly in the real run |
| `main` | confirmation print | `print(f"\nSaved -> {args.output}")` | ✓ COMPLETES CLEANLY | `seasonality_by_week.py:102` — executes after the CSV write succeeds and now returns 0 without raising |

### Behavioral Spot-Checks (real, non-mocked runs against cached data, run independently by this verifier)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `python -m pytest -q` (full suite, run once) | full suite | 320 passed, 2 pre-existing unrelated RuntimeWarnings | ✓ PASS |
| Real run, no `--output`, real cached data (Technology/sp500, 82 tickers, 65 years) | `python seasonality_by_week.py --sector Technology --universe sp500 --bootstrap-iters 200 --seed 1` | Exit 0; header/table/summary printed correctly, 52-row table, 7 significant weeks flagged, caveat present | ✓ PASS |
| Real run WITH `--output`, real cached data (same repro scenario as prior verification's failure) | `python seasonality_by_week.py --sector Technology --universe sp500 --bootstrap-iters 200 --seed 1 --output <path>.csv` | **Exit 0** (was exit 1). `Saved -> <path>` printed. No traceback. CSV verified: 53 lines, 9 columns, content matches stdout table | ✓ PASS (regression from prior FAIL, now fixed) |
| `sys.stdout.encoding` on this machine | `python -c "import sys; print(sys.stdout.encoding)"` | `cp1252` | Confirms the fix was validated on the same real platform condition that reproduced the original crash |
| Arrow character scan | `'→' in open('seasonality_by_week.py').read()` / same for `scan.py`'s print line | `seasonality_by_week.py`: clean. `scan.py:160` print line: clean (ASCII `->`). `scan.py:116` still has one `→` but inside a Python comment, never printed to stdout — not a functional defect | ✓ Confirmed narrowly scoped fix, no residual print-path risk |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|-------------|--------|----------|
| SEAS-10 | 07-01, 07-02 | 52-row table, 9 columns, sorted by week | ✓ SATISFIED | Verified live against real cached data |
| SEAS-11 | 07-01, 07-02 | Summary: baseline, significant weeks/none-message, top-5/bottom-5, caveat | ✓ SATISFIED | Verified live against real cached data |
| SEAS-12 | 07-01, 07-02 | One-line survivorship-bias warning in header | ✓ SATISFIED | Verified live against real cached data |
| SEAS-13 | 07-01, 07-02, quick-260712-h7l | `--output` writes CSV; stdout always happens regardless | ✓ SATISFIED | Previously BLOCKED by an unhandled `UnicodeEncodeError` on the cp1252-encoded confirmation print; fixed by quick task 260712-h7l (ASCII `->` replacement + a real subprocess-based cp1252 regression test). Re-verified end-to-end by this pass with a fresh, independent real run: exit 0, CSV correct, confirmation line printed cleanly. |

**Note on REQUIREMENTS.md:** `.planning/REQUIREMENTS.md`'s traceability table still lists SEAS-10 through SEAS-13 as `Pending` (checkboxes unchecked). This remains a documentation-sync gap only — not a functional blocker — but should be updated to `Complete`/checked now that all four requirements are genuinely satisfied end-to-end.

### Anti-Patterns Found

None (`TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`) in `scanner/seasonality.py`, `seasonality_by_week.py`, `scan.py`, `tests/test_seasonality.py`, `tests/test_seasonality_cli.py`, or `tests/_regression_cp1252_helper.py`.

### Human Verification Required

None — the gap closure is deterministically, programmatically reproducible (this verifier independently re-ran the exact prior-failing scenario and confirmed exit 0, no subjective judgment required).

### Gaps Summary

No gaps remain. Phase 7's core rendering/summary/warning work (SEAS-10, SEAS-11, SEAS-12) continues to work exactly as verified in the prior pass. The one identified gap — SEAS-13's `--output` confirmation print crashing with `UnicodeEncodeError` on cp1252-encoded Windows streams — was fixed by quick task 260712-h7l (commits `ca719f7`, `3693475`, merged via `8661496`, documented in `03e12da`/`78cc1c6`). This verifier independently re-ran the exact repro scenario from the prior failed verification against real cached data on the same cp1252 platform and confirmed the process now exits 0 with a correct confirmation line and no traceback. The full `pytest -q` suite is green at 320 tests (up from 319 — the one new regression test), run once by this verifier rather than trusted from SUMMARY.md.

The new regression test (`test_main_output_survives_cp1252_stream_encoding`) closes the specific test-coverage gap flagged in the prior verification: it runs the real CLI through a subprocess with `PYTHONIOENCODING=cp1252` forced, rather than relying on `capsys`'s encoding-blind in-memory buffer — so this class of bug is now caught by the test suite going forward, not just observed manually.

Phase 7's goal — "Results are presented to the user as a readable per-week table, an interpretive summary with anti-overfitting caveats, and an optional CSV export" — is now fully and genuinely achieved for all four success criteria.

---

_Verified: 2026-07-12T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
