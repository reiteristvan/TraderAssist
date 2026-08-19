---
phase: quick-260819-ko0
plan: 1
subsystem: backtest
tags: [simulate, targets, risk-management, backtest, atr, stop-loss]

# Dependency graph
requires:
  - phase: quick-260819-g5h
    provides: "apply_min_stop_floor / MIN_STOP_ATR_MULT in scanner/targets.py — the close-side 0.5x ATR stop floor this task extends to the entry side"
provides:
  - "Entry-side 0.5x ATR minimum-risk floor in scanner/simulate.py::simulate_trades, applied after the gap_skip_down guard and before risk is computed"
  - "effective_stop drives stop-hit detection, the stop-out exit price, and every R metric (r_multiple, mae_r, mfe_r, target_r, post_stop_mfe_r)"
  - "Regression test block in tests/test_simulate.py covering stop-hit detection, exit-price/denominator agreement, R-compression, guard order, never-tighten, degenerate ATR, and behavioral reuse"
  - "CLAUDE.md documentation of both floor halves and the published-stop vs exit-px divergence consequence"
affects: [winner-loser-analysis, gate-attribution, journal-resolve, backtest-reports]

# Tech tracking
tech-stack:
  added: []
  patterns: ["reuse a single house-rule helper across two application points (close-side and entry-side) rather than duplicating the constant"]

key-files:
  created: []
  modified:
    - scanner/simulate.py
    - tests/test_simulate.py
    - CLAUDE.md

key-decisions:
  - "D-01: widen the stop, never skip the trade — effective_stop = apply_min_stop_floor(sig.stop, entry_px, sig.atr), only ever moves further from entry"
  - "D-02: the widened stop is a REAL stop — stop-hit detection, stop-out exit price, and the risk denominator all switch together (lines 160, 188, 193), so a stop-out remains exactly -1.0R"
  - "D-03: the gap_skip_down guard (line 149) stays on the ORIGINAL published stop; effective_stop is computed AFTER the guard so it can never rescue a gap-skipped trade"
  - "D-04: no schema change, no new column, no new Trade.flags key recording the adjustment; the published-stop vs exit-px divergence is documented, not persisted"
  - "D-05: scanner/targets.py untouched — the close-side floor stays exactly as shipped; scanner/simulate.py imports and reuses apply_min_stop_floor directly, not a local reimplementation"

patterns-established:
  - "House-rule constants (MIN_STOP_ATR_MULT) live in exactly one module and are imported by every application site, never redefined locally"

requirements-completed: [STOP-FLOOR-02]

coverage:
  - id: D1
    description: "Entry-side effective_stop computed via apply_min_stop_floor and switched into risk, stop-hit detection, and stop-out exit price in scanner/simulate.py"
    requirement: "STOP-FLOOR-02"
    verification:
      - kind: unit
        ref: "tests/test_simulate.py#test_ko0_stop_hit_detection_moves_with_widened_stop"
        status: pass
      - kind: unit
        ref: "tests/test_simulate.py#test_ko0_exit_price_and_denominator_agree"
        status: pass
    human_judgment: false
  - id: D2
    description: "gap_skip_down/gap_skip_up guards unchanged — a widened stop cannot rescue a gap-skipped trade"
    requirement: "STOP-FLOOR-02"
    verification:
      - kind: unit
        ref: "tests/test_simulate.py#test_ko0_widened_stop_does_not_rescue_gap_skip_down"
        status: pass
      - kind: unit
        ref: "tests/test_simulate.py#test_ko0_gap_skip_up_untouched"
        status: pass
    human_judgment: false
  - id: D3
    description: "Floor only ever widens; existing fixtures byte-identical; degenerate ATR leaves stop unchanged and never raises"
    requirement: "STOP-FLOOR-02"
    verification:
      - kind: unit
        ref: "tests/test_simulate.py#test_ko0_never_tightens_existing_geometry_byte_identical"
        status: pass
      - kind: unit
        ref: "tests/test_simulate.py#test_ko0_degenerate_atr_leaves_stop_unchanged"
        status: pass
    human_judgment: false
  - id: D4
    description: "Full pytest suite green offline with zero pre-existing expectations changed; golden fixtures, targets.py, store_db.py untouched"
    requirement: "STOP-FLOOR-02"
    verification:
      - kind: unit
        ref: "pytest -q (403 passed)"
        status: pass
    human_judgment: false
  - id: D5
    description: "CLAUDE.md records both floor halves and the published-stop vs exit-px divergence"
    verification: []
    human_judgment: true
    rationale: "Documentation quality/clarity is a human judgment call, not something a test can verify"

duration: 25min
completed: 2026-08-19
status: complete
---

# Quick Task 260819-ko0: Entry-Side Stop Floor in simulate.py Summary

**Widened the simulated trade's risk denominator by re-applying `apply_min_stop_floor` at the entry open, not just at signal close — making the 0.5x ATR minimum-risk floor a real stop (detection + exit price + denominator together) rather than a denominator-only fix.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-19T12:54:00Z
- **Completed:** 2026-08-19T13:19:29Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- `scanner/simulate.py::simulate_trades` now computes `effective_stop = apply_min_stop_floor(sig.stop, entry_px, sig.atr)` immediately after the `gap_skip_down` guard and before `risk` is assigned; the risk denominator, the stop-hit comparison, and the stop-out exit price all read `effective_stop`.
- Added 15 new regression tests in `tests/test_simulate.py` pinning the real-stop contract, guard order, never-tighten property, degenerate-ATR safety, and a unit-level R-compression demonstration (published R ≈100.0 → widened R ≈9.9 on the same synthetic fixture).
- Documented both floor halves (close-side from 260819-g5h, entry-side from this task) and the published-stop vs exit-px divergence consequence in `CLAUDE.md`'s Key Design Decisions table.
- Zero pre-existing test expectations changed — the planning prediction (prior_investigation item 3) held exactly: 388 → 403 tests, all 388 original assertions byte-identical.

## Task Commits

Each task was committed atomically:

1. **Task 1: Compute the entry-side effective stop and switch all three stop-derived use sites** - `ea0cc22` (feat)
2. **Task 2: Pin the real-stop contract, the guard order, and the R-compression demonstration in tests** - `57cf2d7` (test)
3. **Task 3: Assert the full suite is green with no expectation edited, and document the published-stop divergence** - `ef26c0d` (docs)

**Plan metadata:** _pending — this commit_

## Files Created/Modified
- `scanner/simulate.py` - added `apply_min_stop_floor` import, `effective_stop` binding after the gap guard, switched 3 use sites, corrected docstring
- `tests/test_simulate.py` - added 15-test regression block (`test_ko0_*`) covering the full blast radius
- `CLAUDE.md` - extended the stop-rules row into three rows (close-side floor, entry-side floor, shared multiplier) plus a documented-consequence paragraph

## Blast Radius (per plan `<blast_radius>` table, walked row by row)

| Line | Expression | Final Disposition |
|------|-----------|-------------------|
| 138 | `if entry_px >= sig.target` (gap_skip_up) | **UNCHANGED** — verified byte-identical, no stop value involved |
| 149 | `if entry_px <= sig.stop` (gap_skip_down) | **UNCHANGED** — still evaluates the ORIGINAL published stop; `effective_stop` is computed strictly after this line |
| new | `effective_stop = apply_min_stop_floor(sig.stop, entry_px, sig.atr)` | **INSERTED** immediately after the line-149 guard, before the `risk` assignment |
| 160→ | `risk = entry_px - sig.stop` | **SWITCHED** to `entry_px - effective_stop` |
| 162 | `target_r_val = target_dist / risk` | inherits via `risk` — no edit, confirmed unchanged in code |
| 163 | `target_atr_val = target_dist / sig.atr` | **UNCHANGED** — divides by ATR directly, not by stop |
| 188→ | `stop_hit = low <= sig.stop` | **SWITCHED** to `low <= effective_stop` |
| 189 | `target_hit = high >= sig.target` | **UNCHANGED** |
| 193→ | `exit_px_val = sig.stop` | **SWITCHED** to `exit_px_val = effective_stop` |
| 201 | `post_stop_reached_target_val = max_post_high >= sig.target` | **UNCHANGED** |
| 202 | `post_stop_mfe_r_val = (max_post_high - entry_px) / risk` | inherits via `risk` — no edit |
| 225 | `mae_r_val = (min_low - entry_px) / risk` | inherits via `risk` — no edit |
| 226 | `mfe_r_val = (max_high - entry_px) / risk` | inherits via `risk` — no edit |
| 227 | `r_multiple = (exit_px_val - entry_px) / risk` | inherits — both operands now derive from `effective_stop`, so a stop-out is still exactly -1.0R |

**Note on the "one `sig.stop` reference" claim:** after the edit, `sig.stop` appears twice textually in the function body — the line-149 `gap_skip_down` guard (the sole surviving *use site*, as specified), and as the input argument to `apply_min_stop_floor(sig.stop, entry_px, sig.atr)` in the new `effective_stop` binding itself. The latter is not a "use site" in the blast-radius sense (it isn't one of the four original comparisons/assignments being switched) — it is the necessary source value the floor function widens from. All four original use sites (149, 160, 188, 193) are accounted for exactly as specified: one unchanged, three switched.

## Changed Expectations

**None — zero pre-existing test expectations changed.** This matches the planning prediction (prior_investigation item 3) exactly, and was verified rather than assumed:

- Baseline: 388 tests collected before any change.
- `tests/test_simulate.py` and `tests/test_journal.py` (the only two files reaching `simulate_trades`) — both ran green, unmodified, after Task 1: `python -m pytest -q tests/test_simulate.py tests/test_journal.py` → **37 passed**.
- Full suite after Task 1: **388 passed**, 0 failed.
- After Task 2's 15 new tests: **403 passed** (388 + 15), 0 failed, 0 modified.
- The measured cause: every pre-existing fixture in both files uses `stop=90.0, entry_open=100.0` with `atr=1.0` or `atr=1.5`. `apply_min_stop_floor(90.0, 100.0, 1.0)` and `apply_min_stop_floor(90.0, 100.0, 1.5)` both return `90.0` unchanged (floor candidates are 99.5 and 99.25 respectively — far above the published stop, so `min()` keeps the original). The two gap-skip fixtures (`opens` 89.5 and 85.0) are caught by the line-149 guard before `effective_stop` is ever computed.
- `tests/golden/` is **unmodified** (`git diff --stat -- tests/golden/` is empty) and unaffected in principle: golden fixtures encode gate and score fields only, and `evaluate()` (the function under golden test) never reaches `simulate_trades` — the simulator is a downstream backtest/journal component, not part of the gate-evaluation pipeline.

## Circular-Import Answer

**`scanner/targets.py` does NOT import `scanner/simulate.py`, directly or transitively.** Verified two ways:

1. **Static inspection of the import chain:** `scanner/targets.py` imports only `dataclasses`, `math`, `pandas`, and `ta.volatility.AverageTrueRange` at module level; its one intra-package import (`scanner.strategies.pullback`) is lazy, inside `attach_risk()`. Following that chain: `scanner/strategies/pullback.py` imports `scanner.core`, and `scanner/core.py` imports no scanner module at all. `grep -rn simulate scanner/core.py scanner/targets.py scanner/strategies/` returns nothing.
2. **Live execution of both import orders**, both succeeding: `import scanner.simulate; from scanner.targets import MIN_STOP_ATR_MULT` → OK; `import scanner.targets; import scanner.simulate` → OK. The dependency is strictly one-way (`simulate → targets`), and this task's actual edit (`from scanner.targets import apply_min_stop_floor` added to `scanner/simulate.py`) followed that direction exactly — `scanner/targets.py` gained no new import.

## Observed R-Compression Numbers

From `test_ko0_r_compression_sanity_demonstration` (unit-level stand-in for the CONTEXT.md sanity target, run on synthetic bars — no backtest executed):

- Fixture: published stop 99.90, entry open 100.0, ATR 2.0, target 110.0 (target hit).
- **Pre-change (published stop as denominator):** risk = 100.0 − 99.90 = 0.10 → r_multiple = (110.0 − 100.0) / 0.10 = **100.0**.
- **Post-change (effective stop as denominator):** `apply_min_stop_floor(99.90, 100.0, 2.0)` = 98.99 → risk = 100.0 − 98.99 = 1.01 → r_multiple = (110.0 − 100.0) / 1.01 = **9.900990099...** (asserted `pytest.approx(9.9, abs=0.05)` and `< 11`).
- This is a ~10.1x compression on the collapsed fixture, consistent with the CONTEXT.md/PLAN.md order-of-magnitude target (max R falling from 56.0 to roughly 9 on the full reference backtest run).

## Published-Stop vs Exit-Price Divergence

Recorded in `CLAUDE.md`'s Key Design Decisions table (new paragraph immediately below the three stop-floor rows): the `signals.stop` DB column intentionally keeps the published close-based stop — per D-04, no new column was added to record the entry-side widening. For a stop-out trade, `exit_px` is the entry-widened `effective_stop`, which can differ from `signals.stop`. On the reference backtest run (`038a385_2021-01-01_20260819_142048`, pullback/sp600), roughly 14% of trades diverge this way, so `(entry_px − stop) / atr` computed directly from raw `signals` columns will still read below 0.5 for those trades even though the trade was simulated against a wider stop. This is documented as expected behavior, not a bug — the authoritative risk denominator for any stop-out trade is `entry_px − exit_px`, not `entry_px − signals.stop`.

## Decisions Made
- Reused `apply_min_stop_floor` directly (imported, not reimplemented or wrapped) — per CONTEXT.md's discretion note, resolved in favor of maximal reuse since prior_investigation confirmed no circular import risk.
- `effective_stop` is a plain local variable, not extracted into a separate helper function in `simulate.py` — the call site is a single line and a wrapper would add indirection with no behavior of its own (plan explicitly forbade a "thin wrapper").
- Test fixtures for the regression block use a dedicated `_collapsed_signal()` helper (stop=99.90, target=110.0, atr=2.0, entry=100.0) mirroring the plan's chosen geometry, rather than parametrizing the existing `_signal()` helper — keeps the two fixture families visually distinct in the test file.

## Deviations from Plan

None - plan executed exactly as written. All three tasks completed with their exact `<action>` and `<verify>` steps; no Rule 1-4 auto-fixes were needed; no architectural questions arose.

## Known Stubs

None.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. No backtest was run (explicitly out of scope per plan and CLAUDE.md prohibition) — a future backtest run against the reference universe is the user's decision, per CONTEXT.md.

## Next Phase Readiness
- The entry-side stop floor is live in both the backtest path (`scan.py backtest`) and the live journal resolution path (`journal.py:200` calls `simulate_trades` for LIVE signal resolution) — both are affected by this change, as intended.
- The winner/loser analysis pipeline (which surfaced the `rsi_entry < 48.2` false-discovery artifact documented in CONTEXT.md) will now compute R against the corrected denominator on the next backtest run. Re-running the reference backtest and re-validating that rule is a follow-up decision for István, not part of this task.
- No blockers.

---
*Phase: quick-260819-ko0*
*Completed: 2026-08-19*

## Self-Check: PASSED

All created/modified files confirmed present on disk (`scanner/simulate.py`, `tests/test_simulate.py`, `CLAUDE.md`, this SUMMARY). All three task commits confirmed present in git history (`ea0cc22`, `57cf2d7`, `ef26c0d`).
