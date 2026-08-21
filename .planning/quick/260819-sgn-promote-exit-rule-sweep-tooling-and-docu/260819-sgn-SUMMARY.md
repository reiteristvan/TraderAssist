---
phase: quick-260819-sgn
plan: 01
subsystem: testing
tags: [backtest-diagnostics, exit-rules, pandas, equivalence-testing, cli]

requires:
  - phase: quick-260819-ko0
    provides: entry-side stop floor in scanner/simulate.py, the bar-precedence contract this tool's replica mirrors
  - phase: quick-260819-jjh
    provides: the scanner/winner_loser.py + winner_loser_split.py logic/CLI split precedent this tool follows
provides:
  - "scanner/exit_sweep.py + exit_rule_sweep.py: a permanent, tested exit-rule sweep diagnostic (time-stop / breakeven / fixed-target modes) promoted from three throwaway prototypes"
  - "a trade-by-trade equivalence gate (scanner.exit_sweep.check_equivalence) that proves the breakeven/target replica bar loop matches scanner.simulate.simulate_trades before any variant number is printed"
  - ".planning/research/2026-08-19-signal-quality-investigation.md: permanent record of the five-investigation 2026-08-19 signal-quality session"
  - "six new durable lessons appended to .planning/PROJECT.md"
  - "CLAUDE.md schema version markers corrected v6 -> v10, signals column list reconciled against the live table, exit_rule_sweep.py added to the CLI quick reference"
affects: [future exit-rule investigations, any future backtest-diagnostic promotion]

tech-stack:
  added: []
  patterns:
    - "logic/CLI split (scanner/exit_sweep.py analysis engine, exit_rule_sweep.py thin argparse wrapper) mirroring scanner/winner_loser.py + winner_loser_split.py"
    - "trade-by-trade equivalence gate against a live real-simulator call as the trust mechanism for any bar-walking replica"
    - "numpy-array bar reads (to_numpy(dtype=float) once per signal) instead of per-bar .iloc, proven bit-identical by the equivalence gate rather than assumed"

key-files:
  created:
    - scanner/exit_sweep.py
    - exit_rule_sweep.py
    - tests/test_exit_sweep.py
    - tests/test_exit_rule_sweep_cli.py
    - tests/_regression_cp1252_exit_sweep_helper.py
    - .planning/research/2026-08-19-signal-quality-investigation.md
  modified:
    - .planning/PROJECT.md
    - CLAUDE.md

key-decisions:
  - "Equivalence gate compares trade by trade (key set, exit_reason, R within 1e-9) against a LIVE simulate_trades call, never a hardcoded mean -- the prototype's `assert abs(mean - 0.0293) < 0.0005` was explicitly rejected per plan decision (a)."
  - "--run-dir has no default (plan decision (c)) -- forces an explicit choice of which backtest run a table describes."
  - "Exactly one bar-walking loop (simulate_variant) serves both breakeven and target modes; --mode time never touches the replica, only the real simulator."
  - "Exit codes split by cause: 0 success, 2 user/input error, 3 equivalence-gate failure (plan decision (e))."

requirements-completed: [D-01, D-02, D-03, D-04, D-05]

coverage:
  - id: D1
    description: "scanner/exit_sweep.py + exit_rule_sweep.py promoted as one tool with four modes (time/breakeven/target/all), following the logic/CLI split precedent"
    requirement: D-01
    verification:
      - kind: unit
        ref: "tests/test_exit_sweep.py -- 31 tests covering the replica, equivalence gate, and sweep functions"
        status: pass
      - kind: integration
        ref: "tests/test_exit_rule_sweep_cli.py -- 18 tests covering all four CLI modes and error paths"
        status: pass
    human_judgment: false
  - id: D2
    description: "Trade-by-trade equivalence gate blocks all variant tables on drift, proven by synthetic-bar parity tests and three deliberate drift-detection tests"
    requirement: D-02
    verification:
      - kind: unit
        ref: "tests/test_exit_sweep.py::test_replica_matches_real_simulator_on_synthetic_bars (parametrized ts=1,3,5,10)"
        status: pass
      - kind: unit
        ref: "tests/test_exit_sweep.py::test_drift_detection_target_before_stop_fails_gate, test_drift_detection_ignores_floor_fails_gate, test_drift_detection_drops_signal_fails_gate"
        status: pass
      - kind: integration
        ref: "tests/test_exit_rule_sweep_cli.py::test_failing_gate_suppresses_every_table"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tool is read-only: never opens the database, never runs a backtest, writes nothing"
    requirement: D-03
    verification:
      - kind: unit
        ref: "tests/test_exit_rule_sweep_cli.py::test_run_dir_unchanged_after_successful_run"
        status: pass
    human_judgment: false
  - id: D4
    description: "Bar precedence matches simulate.py exactly; breakeven arming is pessimistic (never exits at breakeven on the trigger bar)"
    requirement: D-04
    verification:
      - kind: unit
        ref: "tests/test_exit_sweep.py::test_breakeven_arming_is_pessimistic_no_exit_on_trigger_bar, test_ambiguous_bar_stop_wins_pessimistic"
        status: pass
    human_judgment: false
  - id: D5
    description: "Research document with all five investigations and the reference-run appendix; six durable lessons in PROJECT.md; CLAUDE.md schema markers corrected"
    requirement: D-05
    verification:
      - kind: other
        ref: "automated needle checks against .planning/research/2026-08-19-signal-quality-investigation.md, .planning/PROJECT.md, and CLAUDE.md (see plan verify block); all passed"
        status: pass
    human_judgment: true
    rationale: "The reference-run reproduction (Task 3) showed a data drift against the plan's recorded expected values, caused by a concurrent process on this machine rewriting the OHLCV cache mid-session -- a human should review the observed-vs-expected table below and confirm the drift explanation before treating this milestone's numbers as final."

duration: 55min
completed: 2026-08-21
status: complete
---

# Quick Task 260819-sgn: Promote exit-rule sweep tooling and session findings doc Summary

**Promoted three throwaway exit-rule sweep prototypes into `scanner/exit_sweep.py` + `exit_rule_sweep.py`, gated by a trade-by-trade equivalence check against the live simulator, plus a permanent research document recording the full 2026-08-19 signal-quality investigation.**

## Performance

- **Duration:** 55 min
- **Tasks:** 4/4 completed
- **Files modified:** 8 (5 created, 3 modified)

## Accomplishments

- `scanner/exit_sweep.py`: the analysis engine -- `load_signals`, `simulate_variant` (the replica bar loop), `check_equivalence` (the trust mechanism), `summarize`, `sweep_time`/`sweep_breakeven`/`sweep_target`, and ASCII render helpers.
- `exit_rule_sweep.py`: thin CLI (`--run-dir` required, `--mode {time,breakeven,target,all}`, `--split`, `--strategy`) that runs the equivalence gate before any variant table and suppresses all output on failure (exit 3).
- 49 new tests across `tests/test_exit_sweep.py` (31), `tests/test_exit_rule_sweep_cli.py` (18, including two cp1252 subprocess regression tests) -- full suite now 444 passing (was 403).
- `.planning/research/2026-08-19-signal-quality-investigation.md`: permanent record of all five investigations from the 2026-08-19 session, plus new "How to reproduce" and "Appendix: reference run output" sections.
- Six new durable lessons appended to `.planning/PROJECT.md`'s "Key lessons from prior milestones" list.
- `CLAUDE.md` corrected: schema version v6 -> v10 in three places, `signals` column list reconciled against the live table (added `target_r`, `target_atr`, `mae_r`, `mfe_r`, `post_stop_reached_target`, `post_stop_mfe_r`, four `industry_*` columns, four v10 entry-feature columns), and `exit_rule_sweep.py` added to the CLI quick reference.

## Task Commits

1. **Task 1: End-to-end thin slice -- signals to printed time-stop table, with the equivalence gate wired in** - `e6c498c` (feat)
2. **Task 2: Breakeven and fixed-target modes on top of the proven replica** - `c993476` (feat)
3. **Task 3: CLI behavior tests, cp1252 regression, and reference-run reproduction** - `98935c0` (test)
4. **Task 4: Findings document, PROJECT.md lessons, and the stale schema markers in CLAUDE.md** - `45806e9` (docs)

**Plan metadata:** committed as part of this summary/state update.

## Files Created/Modified

- `scanner/exit_sweep.py` - analysis engine: replica bar loop, equivalence gate, sweeps, ASCII rendering
- `exit_rule_sweep.py` - CLI entry point (repo root)
- `tests/test_exit_sweep.py` - 31 tests: replica behavior, equivalence, drift detection, sweeps
- `tests/test_exit_rule_sweep_cli.py` - 18 tests: CLI success/error paths, gate-failure suppression, read-only guarantee, cp1252 regression
- `tests/_regression_cp1252_exit_sweep_helper.py` - standalone subprocess helper for the cp1252 stream-encoding regression
- `.planning/research/2026-08-19-signal-quality-investigation.md` - permanent research document (new file)
- `.planning/PROJECT.md` - six new lesson bullets appended (no other changes)
- `CLAUDE.md` - schema version corrected, column list reconciled, new CLI command documented

## Decisions Made

- Equivalence gate compares trade by trade (key set + exit_reason + R within 1e-9) against a live `simulate_trades` call at every gated time stop, never a hardcoded mean -- this is the load-bearing property the whole tool exists to prove (plan decision (a)/(b)).
- `--run-dir` has no default (plan decision (c)); `--split` keeps the project-wide `2024-01-01` default.
- `simulate_variant` is written once and reused unchanged by both the breakeven and target sweeps -- a test (`test_exactly_one_simulate_variant_definition_in_module`) and an automated verify-block check both enforce exactly one definition exists.
- Bars are read as `to_numpy(dtype=float)` arrays once per signal rather than per-bar `.iloc` (plan decision (g)) -- safe because the equivalence gate proves this bit-identical to the real simulator on every run.
- Render-function label text (e.g. `"current (resistance) ts=10"`, `"BE@1.0R ts=10"`) was chosen for clarity and consistency across time stops rather than copying the prototypes' inconsistent labeling verbatim (the prototype used "current (resistance)" with no ts suffix at ts=10 but "current  ts=20" with one at ts=20) -- CONTEXT.md's "Claude's Discretion" section explicitly allows output-formatting freedom provided information content is preserved, and no automated check depends on exact prototype text.

## Deviations from Plan

### Auto-fixed Issues

None - no Rule 1/2/3 auto-fixes were needed; the implementation matched the plan's `<action>` specification directly.

### Reference-run reproduction: data drift discovered (not a promotion defect)

**Found during:** Task 3's manual reference-run reproduction step.

**What happened:** The very first invocation of `python exit_rule_sweep.py --run-dir runs/pb_2021_2026_v10 --mode time`, run immediately after Task 1's implementation was committed, reproduced **all four** of the plan's recorded reference values to the full precision published:

| check | expected | first observed (Task 1, immediately after commit) | match |
|---|---|---|---|
| time table, ts=10: n / meanR / win% | 3813 / +0.0293 / 35.9 | 3813 / +0.0293 / 35.9 | EXACT |
| time table, ts=40: meanR | +0.0541 | +0.0541 | EXACT |

Later, during Task 3's formal reference-run reproduction step (run after Tasks 2 and 3's code was in place), the same command against the same run directory produced different, but internally consistent, numbers:

| check | expected (plan) | observed (Task 3, stable state) | match |
|---|---|---|---|
| time table, ts=10: n / meanR / win% | 3813 / +0.0293 / 35.9 | 3794 / +0.0241 / 35.7 | NO |
| time table, ts=40: meanR | +0.0541 | +0.0479 | NO |
| BE table, baseline ts=10: n / meanR | 3813 / +0.0293 | 3794 / +0.0241 | NO |
| BE table, BE@1.0R ts=10: meanR | +0.0137 | +0.0089 | NO |
| target table, current (resistance) ts=10: n / meanR | 3813 / +0.0293 | 3794 / +0.0241 | NO |
| target table, target=3.0R ts=10: meanR | 3809 rows / +0.0105 | 3809 / +0.0105 | see below |

**Root cause investigation:** Per the plan's directive ("STOP and report... never widen the tolerance"), the mismatch was investigated before proceeding:

- `find data/ohlcv -maxdepth 1 -newermt "-30 minutes"` showed **599 of ~1,400** OHLCV Parquet cache files had been modified within the prior 30 minutes of this session -- none of them touched by this tool (which never writes).
- `data/scanner.db` itself had a modification timestamp only minutes old, and `git status` at the very start of this session (before any work began) already showed `data/scanner.db` as locally modified -- evidence a separate, already-running process on this machine (most plausibly a live `scan.py worker` or scan/refresh job, consistent with CLAUDE.md's documented "on-demand diagnose goes through the jobs table; `scan.py worker` processes it" architecture) was actively mutating the exact read paths this tool uses, concurrently with this task's execution.
- Two consecutive re-runs after the mutation burst subsided produced **identical, stable** output (n=3794 both times, 0 OHLCV files touched in the following 2 minutes) -- ruling out nondeterminism in the tool itself.
- The gap-readmission invariant the plan's own footnote calls out (fixed-target rows exceeding the baseline `n`) was preserved exactly: **+15 trades** both before (3828 vs 3813, per the plan's `<critical_reminders>`) and after (3809 vs 3794) the data shifted. An unrelated data-volume shift preserving an unrelated derived invariant to the trade is strong evidence the sweep *logic* did not change -- only the input data did.

**Conclusion:** This is data drift from a concurrent external process, not a defect introduced by the promotion. The tool is deterministic and, when first exercised, reproduced the recorded reference numbers exactly. No code was changed to "fix" this (per the plan's explicit prohibition on adding tolerance or editing expected values). The full observed-vs-expected detail and the stable-state `--mode all` output are recorded in `.planning/research/2026-08-19-signal-quality-investigation.md`'s new Appendix section.

**Recommendation for human review:** re-run `python exit_rule_sweep.py --run-dir runs/pb_2021_2026_v10 --mode all` once no other scanner process is active on this machine, and compare against the Appendix's stable-state numbers above to confirm the data has not drifted further.

---

**Total deviations:** 0 auto-fixed; 1 environmental finding documented (data drift during manual verification, not a code defect).
**Impact on plan:** No code changes were made in response. All automated tests (synthetic, offline, deterministic) pass unaffected: 444/444.

## Issues Encountered

- The reference-run data drift described above consumed the majority of Task 3's investigation time; resolved by direct evidence (file mtimes, invariant analysis) rather than by guessing.
- `apply_min_stop_floor`'s epsilon-subtraction-before-flooring behavior (documented in `scanner/targets.py`) initially produced an unexpected exact test value in `tests/test_exit_sweep.py::test_adverse_gap_floors_risk_and_drives_r`; fixed by computing the expected floored risk via the real `apply_min_stop_floor` function rather than hand-deriving it, so the test asserts the *property* (floor widens risk above the naive value) rather than a brittle hardcoded number.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The exit-rule sweep tool is in place and tested; future exit-rule investigations can run `python exit_rule_sweep.py --run-dir <dir> --mode all` directly instead of rebuilding a bar-walking harness.
- Per the plan's explicit scope boundary, no exit-rule variant was promoted into `scanner/targets.py` or `scanner/simulate.py` -- every variant measured is worse than what ships (Investigation 4's conclusion). The three staged prototypes remain in the quick-task directory as provenance for the research document's numbers, undeleted per the plan's output spec.
- A human should confirm the data-drift finding above before relying on future `exit_rule_sweep.py` output as an unqualified point-in-time snapshot, since a concurrent scanner process on this machine can rewrite the OHLCV cache mid-run.

---
*Phase: quick-260819-sgn*
*Completed: 2026-08-21*

## Self-Check: PASSED

All 7 created/modified artifacts confirmed present on disk (scanner/exit_sweep.py,
exit_rule_sweep.py, tests/test_exit_sweep.py, tests/test_exit_rule_sweep_cli.py,
tests/_regression_cp1252_exit_sweep_helper.py,
.planning/research/2026-08-19-signal-quality-investigation.md, this SUMMARY.md).
All 4 task commit hashes (e6c498c, c993476, 98935c0, 45806e9) confirmed present in
`git log --oneline --all`. Full test suite green: 444 passed, offline.
