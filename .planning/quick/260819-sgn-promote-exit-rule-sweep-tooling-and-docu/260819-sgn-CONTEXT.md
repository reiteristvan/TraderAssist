# Quick Task 260819-sgn: Exit-rule sweep tooling + session findings doc - Context

**Gathered:** 2026-08-19
**Status:** Ready for planning

<domain>
## Task Boundary

Two deliverables from the 2026-08-19 signal-quality investigation:

1. **Promote the three working prototype sweep scripts** into the project as one diagnostic
   tool, following the established CLI/logic split.
2. **Write the session findings document** so the investigation is not lost, and append the
   durable lessons to `PROJECT.md`.

Prototypes staged in this task directory (working, results trusted, treat as reference
implementations): `exit_sweep.py`, `exit_be.py`, `exit_tgt.py`.

</domain>

<decisions>
## Implementation Decisions

### D-01 LOCKED: one tool, not three scripts

- `scanner/exit_sweep.py` - analysis logic (pure, testable, no argparse, no printing)
- `exit_rule_sweep.py` - CLI at repo root

Mirrors `scanner/seasonality.py` + `seasonality_by_week.py` and `scanner/winner_loser.py` +
`winner_loser_split.py`. Tracked in git.

The three prototypes are three MODES of one tool, not three tools:
`--mode {time,breakeven,target,all}` (default `all`).

### D-02 LOCKED: the equivalence gate is the point of this tool

`exit_be.py` and `exit_tgt.py` contain a REPLICA of the bar-precedence loop in
`scanner/simulate.py:196-241` (needed because breakeven and target-override are not parameters
of `simulate_trades`). A replica that silently drifts from the real simulator would produce
confident, wrong answers.

Therefore:

- The time-stop mode MUST use the real `scanner.simulate.simulate_trades` directly - it takes
  `time_stop` as a parameter, so no replica is needed there. Do not reimplement it.
- The replica MUST assert equivalence with the real simulator before reporting anything:
  running the variant with the breakeven rule disabled and no target override must reproduce
  `simulate_trades` output. The prototype asserts `abs(mean - 0.0293) < 0.0005` against a
  hardcoded number; the promoted version must instead compare against a LIVE
  `simulate_trades` call on the same signals, so the gate keeps working when the data changes.
- That equivalence must ALSO be a pytest test, on synthetic bars, so `pytest -q` catches drift
  if `simulate.py` is ever edited again.

This is the single most important requirement in the task.

### D-03 LOCKED: read-only, no DB writes, no backtest

Reads `runs/<dir>/signals.parquet` plus the Parquet OHLCV cache via `data_store.get_history`.
Never writes to `data/scanner.db`. Never runs a backtest.

### D-04 LOCKED: bar-precedence semantics must match simulate.py exactly

Within a bar: stop checked BEFORE target (pessimistic), then `bar_idx == time_stop - 1` closes
at that bar's close. Gap guards: `entry_px >= target` and `entry_px <= stop` both skip the
trade. The entry-side floor `apply_min_stop_floor(sig.stop, entry_px, sig.atr)` applies.

Breakeven arming is PESSIMISTIC: when a bar's high reaches `entry + k * risk`, the stop moves
to entry from the NEXT bar onward, never within the trigger bar itself.

### D-05 LOCKED: findings document

Write `.planning/research/2026-08-19-signal-quality-investigation.md` containing the full
record in the "Session findings" section below, verbatim in substance (formatting may be
improved). Then append the durable one-line lessons to the "Key lessons from prior milestones"
list in `.planning/PROJECT.md` (currently around line 92-98).

### Claude's Discretion

- CLI flag names beyond `--mode`; sensible defaults for `--run-dir` and `--split`
- Function decomposition in `scanner/exit_sweep.py`
- Output formatting, provided information content is preserved

</decisions>

<specifics>
## Session findings - the content for the document

### Context

A 5.5-year pullback backtest (sp600, 2021-01-01 to 2026-06-30, 3,813 qualified resolved
trades) was investigated for sources of edge. Four independent investigations, plus two bugs
found and fixed along the way.

### Investigation 1 - per-ticker winner selection (REJECTED)

**Question:** 140 tickers were net-positive over 2021-2026. Do those specific stocks work?

**Method:** permutation test - shuffle R-multiples across tickers, preserving each ticker's
trade count, and count net-positive tickers under the null.

**Result:** 140 observed net-positive out of 316; **137.4 expected under the null**, 5-95
range [128, 147]. Ticker identity carries no information. Median 11 trades per ticker against
an R standard deviation of 2.49 gives a per-ticker standard error of ~0.75R - far larger than
any real difference.

**Conclusion:** per-ticker selection is noise. Do not build on it.

### Investigation 2 - entry-time feature discrimination (NOTHING SURVIVED)

**Method:** train (2021-2023) / holdout (2024-2026) split. Single-feature threshold rules at
Q1/median/Q3 in both directions, selected on train only, applied unchanged to holdout.
Month-block bootstrap CIs. 12 features, 72 rules.

**Result:** no rule beat the holdout baseline. Spearman rho between train and holdout rule
rankings = -0.135. One rule had a holdout CI excluding zero - `rsi_entry < 48.2`, holdout mean
R +0.580, CI [+0.053, +1.098] - which turned out to be a **measurement artifact**, see
Investigation 5.

Two shipped display features do not rank outcomes consistently:
- `confidence`: HIGH best on train (+0.026), MEDIUM best on holdout (+0.225)
- `industry_above_50ma`: sign flips between windows

### Investigation 3 - quality gate attribution (INCONCLUSIVE, DO NOT CUT)

**Method:** compare qualified trades against near-misses that failed exactly one gate, per
gate, with month-block bootstrap CIs and a train/holdout consistency check. Gate labels
normalized first - "Pullback duration 27d/28d/..." is ONE gate with the value embedded in the
label, not 19 gates.

**Result:**
- Qualified baseline: n=3813, mean R +0.029, **95% CI [-0.195, +0.237]**
- **Every** gate's fail-only group falls inside that CI. Not one separates in either direction.
- **6 of 8** largest gates flip sign between train and holdout. The two that are consistent
  (Market cap, At a logical support level) both say the gate is WORKING.
- The gate stack collectively does something: qualified +0.029 vs the whole near-miss pool
  -0.006.
- `Volume contraction` is the largest single exclusion (7,112 trades) at +0.032 mean R,
  statistically identical to the +0.029 it keeps - the obvious cut candidate. `PROJECT.md`
  already records that this exact removal was tried and reverted for degrading performance,
  as was the ADX gate removal.

**Conclusion:** the dataset cannot support gate-cutting decisions. The baseline CI is ~7x the
effect size being measured.

### Investigation 4 - exit rules (TWO CONSISTENT RESULTS, BOTH "KEEP WHAT YOU HAVE")

Exit-reason composition at the current settings: stop 58.7% at -1.000R (contributing -0.587),
target 21.0% at +2.133R (+0.448), time_stop 20.3% at +0.826R (+0.168).

**4a. Time stop** - mean R by `time_stop`: 5 -> +0.037, 10 (current) -> +0.029, 15 -> +0.046,
20 -> +0.045, 30 -> +0.046, 40 -> +0.054. Holdout improves monotonically (+0.113 -> +0.143)
but the train/holdout **rank ordering is nearly inverted** - train's best (5) is holdout's
second-worst. Not reliable.

**4b. Breakeven stops - REFUTED, and worse than baseline everywhere.** Predicted +0.13R on the
reasoning that 22.3% of stop-outs reached +1R before reversing. Measured:

| variant (ts=10) | mean R | train | holdout | win% |
|---|---|---|---|---|
| baseline | **+0.029** | -0.113 | **+0.113** | 35.9 |
| BE @1.0R | +0.014 | -0.118 | +0.092 | 29.2 |
| BE @1.5R | +0.011 | -0.107 | +0.081 | 32.3 |
| BE @2.0R | +0.007 | -0.119 | +0.081 | 33.6 |

Worse still at longer holds (ts=20: +0.045 -> +0.018; ts=40: +0.054 -> +0.013). **The
prediction was one-sided** - it counted the trades that give back a gain but not the ones that
dip toward entry and then run to target. The strategy's entire expectancy comes from the 21%
that reach target at +2.13R, and a breakeven stop scratches exactly those. This is a
consistent, directionally stable negative result across both windows.

**4c. Fixed R-multiple targets - worse than the current resistance-aware target.** Replacing
`compute_targets` output with `entry + k * risk`:

| variant (ts=10) | mean R | train | holdout |
|---|---|---|---|
| current (resistance-aware) | **+0.029** | -0.113 | **+0.113** |
| target = 2.0R | -0.016 | -0.102 | +0.035 |
| target = 3.0R | +0.012 | -0.114 | +0.087 |
| target = 4.0R | +0.017 | -0.108 | +0.091 |

Every fixed multiple loses on both windows at both time stops. **`compute_targets`'
resistance-aware logic is earning its place** - a positive finding about existing code.

### Investigation 5 - two bugs found and fixed

**5a. Degenerate risk denominator at signal close** (fixed, quick task 260819-g5h). The
pullback stop `EMA20 - ATR` and breakout stop `high20 - 0.5*ATR` had no minimum distance from
entry. 15 trades had `|R| > 10`; max `target_r` reached 4,128,767. EPAC 2024-01-16 entered at
28.91 with a stop at 28.89 - 2.4 cents against a 0.71 ATR - producing 72.7R. Those 15 trades
flipped the strategy's sign: raw mean R +0.051 versus -0.007 winsorized at 10R. Fixed with a
0.5x ATR floor in `targets.py`.

**5b. The same collapse at entry** (fixed, quick task 260819-ko0). The close-side floor
guaranteed `close - stop >= 0.5*ATR`, but R is computed from `entry_px` (next open). An
adverse overnight gap re-collapsed the denominator, and the close-side floor made it worse by
pinning a whole population at exactly 0.5x ATR where any negative gap pushes under. 551 trades
(14.4%) still had entry-side risk below 0.5x ATR, minimum 0.0028.

**This manufactured a false discovery.** The `rsi_entry < 48.2` rule from Investigation 2 was
not a profitability filter - it was a detector for mismeasured trades. Low RSI means a deeper
pullback, which is exactly when the close-side floor binds: **78.1%** of that subset sat pinned
at the floor versus 3.0% of the rest, and 38.9% had entry-side risk below 0.5x ATR versus
7.4%. Winsorized at +-2R the subset was WORSE than the rest (-0.197 vs -0.082).

Fixed by widening the stop at entry in `simulate.py`. Decision was widen rather than skip: the
551 affected trades are 82.9% losers (457 losers, 94 winners) but score +0.152 mean R against
+0.014 for the trades that would have been kept, once measured on a corrected risk basis.

**Metric health before and after:** max R 56.0 -> 8.74; `|R|>10` 11 -> 0; raw mean R vs
winsorized-at-5R +0.064/-0.010 -> +0.029/+0.016. **Raw and winsorized now converge** - that
convergence is the signal the metric is trustworthy, more than the level itself.

### The unifying finding

Four independent attempts to locate an edge, all negative in the same way. The reason is
measurement precision, not the specific hypotheses:

- baseline 95% CI is **+-0.2R**; the effects being hunted are **~0.03R**
- the regime term swamps both - train -0.113 vs holdout +0.113 is a 0.23R swing from nothing
  but *when* the trade was taken
- with strong time-clustering, ~3,800 trades give roughly **66 independent monthly blocks**

No amount of re-parameterizing this strategy escapes that constraint.

### Next steps (in the order recommended)

1. **Backtest the breakout strategy properly.** The DB holds exactly one breakout run - 1,162
   signals from a 2024 start - against five-plus pullback runs. Half the system is
   effectively untested, and it is a different edge source rather than another parameter on
   the same one.
2. **Widen the universe** to sp500 + sp400 alongside sp600. It will not add independent time
   blocks, but it sharpens the per-date cross-sectional estimate.
3. **Consider that the pullback strategy as specified is roughly breakeven** (+0.029R, 36% win
   rate, CI spanning zero) and that a structural change may be needed rather than a parametric
   one.

Explicitly NOT recommended: cutting quality gates, adding an RSI entry gate, adding breakeven
stops, or replacing the resistance-aware target with a fixed R multiple. All four are
contradicted by the evidence above.

### Durable lessons for PROJECT.md

Append to the "Key lessons from prior milestones" list:

- Winsorized vs raw mean R divergence is the fastest tell that a risk denominator is
  collapsing - check it before trusting any expectancy figure
- A stop floor must be applied at BOTH signal close and entry fill; flooring only at close
  pins a population at the minimum where any adverse gap re-collapses the denominator
- Selecting anything (tickers, features, gates, exit parameters) on in-sample performance
  reproduces the same failure every time - train/holdout separation is mandatory, and most
  candidates flip sign
- At ~3,800 trades with heavy time clustering the baseline CI is ~+-0.2R, roughly 7x the
  effect sizes being tested - gate and parameter attribution is not resolvable at this sample
  size
- Breakeven stops degrade this strategy at every trigger level tested; its expectancy comes
  from the ~21% of trades that reach target at ~+2.1R
- The resistance-aware target from `compute_targets` beats every fixed R-multiple target
  tested, on both train and holdout

</specifics>

<canonical_refs>
## Canonical References

- `.planning/quick/260819-sgn-.../exit_sweep.py`, `exit_be.py`, `exit_tgt.py` - the working
  prototypes
- `scanner/simulate.py:196-241` - the bar-precedence loop the replica must match
- `seasonality_by_week.py` + `scanner/seasonality.py`, `winner_loser_split.py` +
  `scanner/winner_loser.py` - the CLI/logic split precedent
- `tests/test_seasonality.py` - test structure and the cp1252 subprocess regression pattern
- `runs/pb_2021_2026_v10/signals.parquet` - the reference signal set (git_hash b19b16b)
- `.planning/PROJECT.md` - "Key lessons from prior milestones" list to append to

</canonical_refs>
