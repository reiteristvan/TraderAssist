---
phase: quick-260819-jjh
plan: 01
subsystem: analysis
tags: [sqlite, backtest-diagnostics, statistics, train-holdout, bootstrap]

requires: []
provides:
  - "scanner/winner_loser.py — read-only train/holdout feature-separation analysis engine"
  - "winner_loser_split.py — CLI wrapper, mirrors seasonality_by_week.py's thin-CLI shape"
  - "store_db.get_readonly_connection / store_db.get_analysis_signals — read-only, schema-drift-tolerant query helpers"
affects: [future-backtests, feature-selection]

tech-stack:
  added: []
  patterns:
    - "logic/CLI split (scanner/*.py pure + root *.py thin argparse), same as scanner/seasonality.py + seasonality_by_week.py"
    - "PRAGMA table_info(signals) column-intersection probe so a read-only diagnostic survives a schema the DDL is ahead of"
    - "cp1252 subprocess regression test (not capsys) for every new print surface"

key-files:
  created:
    - scanner/winner_loser.py
    - winner_loser_split.py
    - tests/test_winner_loser.py
    - tests/test_winner_loser_cli.py
    - tests/_regression_cp1252_winner_loser_helper.py
  modified:
    - scanner/store_db.py
    - CLAUDE.md

key-decisions:
  - "All SQL (including the read-only connection helper) lives in store_db.py — no exception carved out for analysis-only reads"
  - "--strategy earns its place: prevents a mixed-strategy run from silently reporting a pullback-only rule as if it covered the whole run"
  - "Preserved the prototype's non-interpolated quantile index formula and pure-python statistics.mean verbatim — the reference threshold atr_pct >= 3.47 depends on it"

requirements-completed: [D-01, D-02, D-03, D-04, D-05, D-06]

coverage:
  - id: D1
    description: "winner_loser_split.py --run-id prints train/holdout counts, both baselines with bootstrap CIs, categorical breakdown, top-N rules scored on holdout, and Spearman rho — all ASCII"
    requirement: "D-06"
    verification:
      - kind: unit
        ref: "tests/test_winner_loser_cli.py::test_cli_survives_cp1252_stream_encoding_success_path"
        status: pass
      - kind: integration
        ref: "manual: python winner_loser_split.py --run-id 4f4fe68_2021-01-01_20260702_090418"
        status: pass
    human_judgment: false
  - id: D2
    description: "Threshold selection reads train rows only; holdout is structurally unreachable from select_rules"
    requirement: "D-05"
    verification:
      - kind: unit
        ref: "tests/test_winner_loser.py::test_select_rules_signature_has_no_holdout_parameter"
        status: pass
      - kind: unit
        ref: "tests/test_winner_loser.py::test_perturbing_holdout_r_leaves_selected_rules_bit_identical"
        status: pass
    human_judgment: false
  - id: D3
    description: "A feature absent from the schema, or with <200 non-null train values, is named as skipped with a distinct reason; test count reflects only tested features"
    requirement: "D-04"
    verification:
      - kind: unit
        ref: "tests/test_winner_loser.py::test_analyze_missing_columns_reported_with_distinct_reason"
        status: pass
      - kind: unit
        ref: "tests/test_winner_loser.py::test_select_rules_skips_feature_with_fewer_than_200_non_null"
        status: pass
    human_judgment: false
  - id: D4
    description: "Unknown run_id, missing DB file, or malformed --split exits 2 with one clear stderr line, never a traceback or NaN table"
    requirement: "D-03"
    verification:
      - kind: unit
        ref: "tests/test_winner_loser_cli.py::test_unknown_run_id_exits_2_names_run_id_no_table"
        status: pass
      - kind: unit
        ref: "tests/test_winner_loser_cli.py::test_missing_db_file_exits_2_names_path"
        status: pass
    human_judgment: false
  - id: D5
    description: "Database is opened read-only via the mode=ro URI and is byte-identical after a run"
    requirement: "D-02"
    verification:
      - kind: unit
        ref: "tests/test_winner_loser_cli.py::test_db_file_bytes_identical_after_successful_run"
        status: pass
    human_judgment: false
  - id: D6
    description: "On the reference run with the legacy 8 features, the promoted code reproduces the prototype's published numbers exactly"
    requirement: "D-01"
    verification:
      - kind: unit
        ref: "tests/test_winner_loser.py::test_reference_run_parity_with_prototype_legacy_features"
        status: pass
    human_judgment: false

duration: ~55min
completed: 2026-08-19
status: complete
---

# Quick Task 260819-jjh: winner_loser_split.py diagnostic CLI Summary

**Promoted the throwaway winner/loser prototype into `scanner/winner_loser.py` + `winner_loser_split.py`, a permanent read-only CLI diagnostic that reproduces the prototype's published reference-run numbers exactly (train n=1404, holdout n=2409, best rule `atr_pct >= 3.47`, Spearman rho=-0.455).**

## Performance

- **Duration:** ~55 min
- **Tasks:** 4/4 complete
- **Files modified:** 7 (2 created source, 1 created CLI, 3 test files, 1 store_db.py addition, CLAUDE.md doc line)

## Accomplishments

- `scanner/store_db.py` gained `get_readonly_connection` (SQLite `mode=ro` URI, never creates or migrates the file) and `get_analysis_signals` (probes `PRAGMA table_info(signals)` and intersects with the wanted column list, so the tool survives a schema the code's DDL is ahead of — the real value here is distinguishing "column absent" from "value NULL" for the caller).
- `scanner/winner_loser.py`: the full analysis engine — `load_records`, `split_records` (D-06 `>=` boundary), month-block `bootstrap_ci`, the prototype's non-interpolated `quantile`, train-only `select_rules` (holdout structurally unreachable — its signature has no holdout parameter), `score_on_holdout`, `spearman_rho`, `analyze` orchestrator, and `render_report` (ASCII-only string builder).
- `winner_loser_split.py`: thin CLI (`--run-id`, `--split`, `--db`, `--top`, `--strategy`), mirroring `seasonality_by_week.py`'s shape — argparse + print, no logic.
- 30 new tests across `tests/test_winner_loser.py` (21) and `tests/test_winner_loser_cli.py` (9), plus a self-contained `tests/_regression_cp1252_winner_loser_helper.py` subprocess helper.
- Full suite: `pytest -q` → **388 passed** (358 pre-existing + 30 new).

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end thin slice** — `79a510a` (feat)
2. **Task 2: Analysis engine** — `bac56ab` (test, RED) → `038a385` (feat, GREEN)
3. **Task 3: ASCII report rendering, CLI error paths, cp1252 gate** — `1a56f3e` (test, RED) → `3a5cef4` (feat, GREEN)
4. **Task 4: Reference-run parity, docs, full suite** — `7418cc3` (test — parity gate + CLAUDE.md doc line)

_No plan-metadata docs commit made — per the dispatch constraints, SUMMARY.md/STATE.md are handled by the orchestrator, not committed by this executor._

## Files Created/Modified

- `scanner/store_db.py` - Added `get_readonly_connection` and `get_analysis_signals` (all SQL stays in this module per convention, no exception carved out)
- `scanner/winner_loser.py` - New: full analysis engine (constants, record loading, split, bootstrap, rule selection, holdout scoring, rho, report rendering)
- `winner_loser_split.py` - New: thin CLI wrapper
- `tests/test_winner_loser.py` - New: 21 tests (engine behavior + Task 4 reference-run parity, skip-gated on `data/scanner.db` presence)
- `tests/test_winner_loser_cli.py` - New: 9 tests (tracer, error paths, report content, byte-identity, cp1252 regression x2)
- `tests/_regression_cp1252_winner_loser_helper.py` - New: self-contained subprocess helper for the cp1252 gate
- `CLAUDE.md` - Added one line to the CLI quick reference block

## Decisions Made

- **All SQL in `store_db.py`, no exception** — `get_readonly_connection` and `get_analysis_signals` both live there; `scanner/winner_loser.py` never writes a SQL string. This was a locked decision from `<decisions_resolved>` in the plan, not something discovered during execution.
- **`--strategy` earns its place** — also locked in the plan; implemented as specified (four-line SQL filter, no dilution of a mixed-strategy run's `pullback_depth_pct` coverage).
- **`analyze()` gained `run_id`/`db_path`/`strategy` keyword parameters** beyond the plan's literal signature list (`split, features, top, iters, seed, missing_columns`) — needed so `WinnerLoserResult` (which the plan explicitly says must carry `run_id, db path, split, strategy filter, ...`) can actually be populated by the function that builds it. This is a direct, non-architectural consequence of the plan's own stated dataclass fields, not a new design decision.

## Deviations from Plan

### Auto-fixed / Adjusted Issues

**1. [Rule 1 - discovered-state drift, test adjusted] Live database migrated from schema v9 to v10 between planning and Task 4**

- **Found during:** Task 4 (reference-run parity)
- **Issue:** The plan's `<discovered_state>` recorded `data/scanner.db` as schema v9 with the four v10 columns (`rsi_entry`, `rvol`, `pullback_depth_pct`, `pct_to_52w_high`) physically **absent**, verified 2026-08-19 before planning. By the time Task 4 ran (same day, later session), some other process (not this task — the tool is read-only, byte-identity is asserted in a test) had triggered `store_db.migrate()`'s lazy v10 migration: `schema_version` is now `10` and the four columns physically exist. For the specific reference run (`4f4fe68_2021-01-01_20260702_090418`, predates v10 feature computation), all four are still 100% NULL — so `select_rules` correctly reports them skipped via the "too few non-null" path (0 non-null) instead of the "column absent" path. Both paths are real, distinct, and already independently tested (the absent-column path is proven synthetically in `test_analyze_missing_columns_reported_with_distinct_reason`, decoupled from the live DB's mutable migration state).
- **Fix:** No code change — this is correct behavior given the current DB state. Adjusted `test_reference_run_coverage_line_twelve_defined_eight_tested_four_skipped` (Task 4) to accept either valid skip-reason wording (`"absent"` or `"non-null"`) instead of hardcoding "absent", with a docstring explaining the drift. The coverage counts themselves (12 defined / 8 tested / 4 skipped) are unaffected and still verified exactly.
- **Files modified:** `tests/test_winner_loser.py`
- **Verification:** All 9 reference-run parity numbers (train n, holdout n, both baselines, enumerated test count, best rule feature/threshold/train R/holdout R, Spearman rho) reproduce the prototype's published values exactly — see the Reference-Run Parity table below. This confirms the drift is cosmetic (which skip-reason string applies) and does not touch the actual analysis output.
- **Committed in:** `7418cc3` (Task 4 commit)

---

**Total deviations:** 1 (discovered-state drift, test wording adjusted — no analysis-code change)
**Impact on plan:** None on correctness. All 9 reference-run parity values match exactly; the only difference from the plan's anticipated wording is which of two already-implemented, already-tested skip-reason strings a stale run happens to trigger given the live DB's current (mutable, external) migration state.

## Reference-Run Parity (Task 4)

Run against `data/scanner.db`, `run_id=4f4fe68_2021-01-01_20260702_090418`, `split=2024-01-01`, `seed=11`, `features=LEGACY_FEATURES` (isolates the promotion/refactor from the schema-v10 feature addition):

| Quantity | Expected (prototype) | Observed (promoted code) | Match |
|---|---|---|---|
| train n | 1404 | 1404 | yes |
| holdout n | 2409 | 2409 | yes |
| train baseline mean R | -0.136 | -0.136 | yes |
| holdout baseline mean R | +0.159 | +0.159 | yes |
| enumerated tests | 48 | 48 | yes |
| best train rule | `atr_pct >= 3.47` | `atr_pct >= 3.473` (Q3) | yes |
| that rule, train mean R | +0.026 | +0.026 | yes |
| that rule, holdout mean R | -0.085 | -0.085 | yes |
| Spearman rho | -0.455 | -0.455 (over 45 rules) | yes |

All nine values match. No code was adjusted to force agreement — this is the un-massaged first run of the promoted code against the reference run. This parity check is encoded as `test_reference_run_parity_with_prototype_legacy_features` in `tests/test_winner_loser.py`, skip-gated (`pytest.mark.skipif`) on the presence of `data/scanner.db` and the reference run, so `pytest -q` stays green on a clean offline checkout.

Coverage on this same run (default `FEATURES`, all twelve): **12 defined, 8 tested, 4 skipped** — the four v10 features, all skipped with the "too few non-null" reason (0 non-null for this pre-v10 run; see Deviations above for why this differs from the plan's anticipated "column absent" wording).

## Known Stubs

None — no hardcoded empty values, placeholder text, or unwired data sources. The tool is fully wired end-to-end against the live database and produces real output on every path.

## Issues Encountered

None beyond the discovered-state drift documented above under Deviations.

## CLAUDE.md drift noted, not fixed (out of scope per plan)

Per Task 4's explicit instruction ("If you notice other drift in CLAUDE.md while you are in there... note it in the SUMMARY rather than fixing it here"): the `## DB schema — scanner.db (v6)` heading in `CLAUDE.md` is stale — the live schema (and `store_db.py`'s `_SCHEMA_VERSION`) is now v10, not v6. A future task should update that heading and its column list (it currently omits `target_r`, `target_atr`, `mae_r`, `mfe_r`, `post_stop_reached_target`, `post_stop_mfe_r`, `industry_group`, `industry_momentum`, `industry_above_50ma`, `industry_rank_pct`, `rsi_entry`, `rvol`, `pullback_depth_pct`, `pct_to_52w_high`).

## Next Phase Readiness

- `winner_loser_split.py` is ready to re-run against any future backtest run_id, from any session, without re-reading this task's context.
- Not in scope (per plan `<output>`, noted for the future): multi-fold or rolling-window validation. The single 2024-01-01 split conflates "does this generalize" with "did the regime change" (train -0.136 vs holdout +0.159). Worth building only if something survives the simple version first.

---
*Phase: quick-260819-jjh*
*Completed: 2026-08-19*

## Self-Check: PASSED

All created files verified present on disk (scanner/winner_loser.py, winner_loser_split.py,
tests/test_winner_loser.py, tests/test_winner_loser_cli.py,
tests/_regression_cp1252_winner_loser_helper.py, this SUMMARY.md). All 6 task/gate commits
(79a510a, bac56ab, 038a385, 1a56f3e, 3a5cef4, 7418cc3) verified present in git log.
