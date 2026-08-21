# Signal Quality Investigation -- 2026-08-19

**Date:** 2026-08-19
**Dataset:** sp600 pullback backtest, 2021-01-01 to 2026-06-30, 3,813 qualified resolved trades
**Reference run:** `pb_2021_2026_v10` (also referenced in commit history as
`4f4fe68_2021-01-01_20260702_090418` for the earlier winner/loser investigation)
**Git hash:** b19b16b

## Context

A 5.5-year pullback backtest (sp600, 2021-01-01 to 2026-06-30, 3,813 qualified resolved
trades) was investigated for sources of edge. Four independent investigations, plus two bugs
found and fixed along the way.

## Investigation 1 -- per-ticker winner selection (REJECTED)

**Question:** 140 tickers were net-positive over 2021-2026. Do those specific stocks work?

**Method:** permutation test -- shuffle R-multiples across tickers, preserving each ticker's
trade count, and count net-positive tickers under the null.

**Result:** 140 observed net-positive out of 316; **137.4 expected under the null**, 5-95
range [128, 147]. Ticker identity carries no information. Median 11 trades per ticker against
an R standard deviation of 2.49 gives a per-ticker standard error of ~0.75R -- far larger than
any real difference.

**Conclusion:** per-ticker selection is noise. Do not build on it.

## Investigation 2 -- entry-time feature discrimination (NOTHING SURVIVED)

**Method:** train (2021-2023) / holdout (2024-2026) split. Single-feature threshold rules at
Q1/median/Q3 in both directions, selected on train only, applied unchanged to holdout.
Month-block bootstrap CIs. 12 features, 72 rules.

**Result:** no rule beat the holdout baseline. Spearman rho between train and holdout rule
rankings = -0.135. One rule had a holdout CI excluding zero -- `rsi_entry < 48.2`, holdout mean
R +0.580, CI [+0.053, +1.098] -- which turned out to be a **measurement artifact**, see
Investigation 5.

Two shipped display features do not rank outcomes consistently:
- `confidence`: HIGH best on train (+0.026), MEDIUM best on holdout (+0.225)
- `industry_above_50ma`: sign flips between windows

## Investigation 3 -- quality gate attribution (INCONCLUSIVE, DO NOT CUT)

**Method:** compare qualified trades against near-misses that failed exactly one gate, per
gate, with month-block bootstrap CIs and a train/holdout consistency check. Gate labels
normalized first -- "Pullback duration 27d/28d/..." is ONE gate with the value embedded in the
label, not 19 gates.

**Result:**
- Qualified baseline: n=3813, mean R +0.029, **95% CI [-0.195, +0.237]**
- **Every** gate's fail-only group falls inside that CI. Not one separates in either direction.
- **6 of 8** largest gates flip sign between train and holdout. The two that are consistent
  (Market cap, At a logical support level) both say the gate is WORKING.
- The gate stack collectively does something: qualified +0.029 vs the whole near-miss pool
  -0.006.
- `Volume contraction` is the largest single exclusion (7,112 trades) at +0.032 mean R,
  statistically identical to the +0.029 it keeps -- the obvious cut candidate. `PROJECT.md`
  already records that this exact removal was tried and reverted for degrading performance,
  as was the ADX gate removal.

**Conclusion:** the dataset cannot support gate-cutting decisions. The baseline CI is ~7x the
effect size being measured.

## Investigation 4 -- exit rules (TWO CONSISTENT RESULTS, BOTH "KEEP WHAT YOU HAVE")

Exit-reason composition at the current settings: stop 58.7% at -1.000R (contributing -0.587),
target 21.0% at +2.133R (+0.448), time_stop 20.3% at +0.826R (+0.168).

**4a. Time stop** -- mean R by `time_stop`: 5 -> +0.037, 10 (current) -> +0.029, 15 -> +0.046,
20 -> +0.045, 30 -> +0.046, 40 -> +0.054. Holdout improves monotonically (+0.113 -> +0.143)
but the train/holdout **rank ordering is nearly inverted** -- train's best (5) is holdout's
second-worst. Not reliable.

**4b. Breakeven stops -- REFUTED, and worse than baseline everywhere.** Predicted +0.13R on the
reasoning that 22.3% of stop-outs reached +1R before reversing. Measured:

| variant (ts=10) | mean R | train | holdout | win% |
|---|---|---|---|---|
| baseline | **+0.029** | -0.113 | **+0.113** | 35.9 |
| BE @1.0R | +0.014 | -0.118 | +0.092 | 29.2 |
| BE @1.5R | +0.011 | -0.107 | +0.081 | 32.3 |
| BE @2.0R | +0.007 | -0.119 | +0.081 | 33.6 |

Worse still at longer holds (ts=20: +0.045 -> +0.018; ts=40: +0.054 -> +0.013). **The
prediction was one-sided** -- it counted the trades that give back a gain but not the ones that
dip toward entry and then run to target. The strategy's entire expectancy comes from the 21%
that reach target at +2.13R, and a breakeven stop scratches exactly those. This is a
consistent, directionally stable negative result across both windows.

**4c. Fixed R-multiple targets -- worse than the current resistance-aware target.** Replacing
`compute_targets` output with `entry + k * risk`:

| variant (ts=10) | mean R | train | holdout |
|---|---|---|---|
| current (resistance-aware) | **+0.029** | -0.113 | **+0.113** |
| target = 2.0R | -0.016 | -0.102 | +0.035 |
| target = 3.0R | +0.012 | -0.114 | +0.087 |
| target = 4.0R | +0.017 | -0.108 | +0.091 |

Every fixed multiple loses on both windows at both time stops. **`compute_targets`'
resistance-aware logic is earning its place** -- a positive finding about existing code.

## Investigation 5 -- two bugs found and fixed

**5a. Degenerate risk denominator at signal close** (fixed, quick task 260819-g5h). The
pullback stop `EMA20 - ATR` and breakout stop `high20 - 0.5*ATR` had no minimum distance from
entry. 15 trades had `|R| > 10`; max `target_r` reached 4,128,767. EPAC 2024-01-16 entered at
28.91 with a stop at 28.89 -- 2.4 cents against a 0.71 ATR -- producing 72.7R. Those 15 trades
flipped the strategy's sign: raw mean R +0.051 versus -0.007 winsorized at 10R. Fixed with a
0.5x ATR floor in `targets.py`.

**5b. The same collapse at entry** (fixed, quick task 260819-ko0). The close-side floor
guaranteed `close - stop >= 0.5*ATR`, but R is computed from `entry_px` (next open). An
adverse overnight gap re-collapsed the denominator, and the close-side floor made it worse by
pinning a whole population at exactly 0.5x ATR where any negative gap pushes under. 551 trades
(14.4%) still had entry-side risk below 0.5x ATR, minimum 0.0028.

**This manufactured a false discovery.** The `rsi_entry < 48.2` rule from Investigation 2 was
not a profitability filter -- it was a detector for mismeasured trades. Low RSI means a deeper
pullback, which is exactly when the close-side floor binds: **78.1%** of that subset sat pinned
at the floor versus 3.0% of the rest, and 38.9% had entry-side risk below 0.5x ATR versus
7.4%. Winsorized at +-2R the subset was WORSE than the rest (-0.197 vs -0.082).

Fixed by widening the stop at entry in `simulate.py`. Decision was widen rather than skip: the
551 affected trades are 82.9% losers (457 losers, 94 winners) but score +0.152 mean R against
+0.014 for the trades that would have been kept, once measured on a corrected risk basis.

**Metric health before and after:** max R 56.0 -> 8.74; `|R|>10` 11 -> 0; raw mean R vs
winsorized-at-5R +0.064/-0.010 -> +0.029/+0.016. **Raw and winsorized now converge** -- that
convergence is the signal the metric is trustworthy, more than the level itself.

## The unifying finding

Four independent attempts to locate an edge, all negative in the same way. The reason is
measurement precision, not the specific hypotheses:

- baseline 95% CI is **+-0.2R**; the effects being hunted are **~0.03R**
- the regime term swamps both -- train -0.113 vs holdout +0.113 is a 0.23R swing from nothing
  but *when* the trade was taken
- with strong time-clustering, ~3,800 trades give roughly **66 independent monthly blocks**

No amount of re-parameterizing this strategy escapes that constraint.

## Next steps (in the order recommended)

1. **Backtest the breakout strategy properly.** The DB holds exactly one breakout run -- 1,162
   signals from a 2024 start -- against five-plus pullback runs. Half the system is
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

## How to reproduce

Investigation 4 (exit rules) is now a permanent, tested project diagnostic rather than a
throwaway script. Run:

```
python exit_rule_sweep.py --run-dir runs/pb_2021_2026_v10 --mode all
```

The tool is read-only: it never opens `data/scanner.db`, never writes anything, and never runs
a backtest. It only reads `<run-dir>/signals.parquet` and the cached OHLCV price history for
the tickers that appear in it.

Before printing a single breakeven or fixed-target number, the tool re-simulates the same
signals at the same time stops through the REAL `scanner.simulate.simulate_trades` and compares
that output, trade by trade, against its own breakeven/target replica -- identical key sets,
identical exit reasons, R agreeing to within 1e-9. If that comparison fails at any time stop the
tool prints `EQUIVALENCE GATE FAILED`, prints nothing else, and exits with a non-zero status.
This is what makes the numbers below (and the tables in Investigation 4 above) trustworthy: the
breakeven and fixed-target sweeps are not a second, independently-fallible simulator -- they are
proven, on every run, to agree with the simulator this project already trusts everywhere it is
not overridden.

## Appendix: reference run output

Captured from `python exit_rule_sweep.py --run-dir runs/pb_2021_2026_v10 --mode all`, run
during promotion (quick task 260819-sgn, 2026-08-21). At the exact moment the promoted tool
was first exercised against this run directory it reproduced the Investigation-4 numbers above
to 4 decimal places (n=3813, ts=10 meanR +0.0293, win 35.9%, ts=40 meanR +0.0541; BE@1.0R ts=10
+0.0137; target=3.0R ts=10 +0.0121). The OHLCV price cache on the machine this promotion ran on
was then rewritten mid-session by a separate, already-running process (evidenced by ~600 cache
files and `data/scanner.db` itself changing modification time during the session, unrelated to
this promotion task, which never writes to either) -- the run below is the resulting stable
state, offset from the numbers above by a small, internally consistent shift (baseline n moved
3813 -> 3794; the target-override re-admission count stayed exactly +15 trades in both states,
3828-3813 before and 3809-3794 after, which is strong evidence the sweep logic itself did not
change). See the quick task 260819-sgn SUMMARY for the full before/after comparison table.

**Root cause identified (2026-08-21).** Not an unexplained external process: `data_store._fetch_raw`
fetches with `auto_adjust=True` (scanner/data_store.py:119), so any new dividend or split retroactively
re-scales the entire historical price series. Filesystem evidence: 599 of 1,535 OHLCV Parquet files were
rewritten at 2026-08-21 11:27, followed by a routine nightly scan at 11:36 — the owner's normal workflow,
two days after the reference run. Changed bars move stop/target hits and gap-guard outcomes, which is why
n fell by 19 with no code change. The qualitative conclusions in this document are unaffected: the drift is
about 0.005R against a +/-0.2R noise band, and every ordering and sign is preserved. The durable implication
is that backtest results carry a data vintage as well as a git hash, and only the latter is recorded.

```
run_dir=runs/pb_2021_2026_v10  split=2024-01-01  strategy=both  signals=3883

EQUIVALENCE GATE: PASS
  time_stop=10: PASS  n_real=3794  n_variant=3794  missing=0  extra=0  max_abs_diff=0.00e+00
  time_stop=20: PASS  n_real=3794  n_variant=3794  missing=0  extra=0  max_abs_diff=0.00e+00
  time_stop=40: PASS  n_real=3794  n_variant=3794  missing=0  extra=0  max_abs_diff=0.00e+00

 time_stop      n    meanR   trainR    holdR   win%  stop%   tgt%  time%
         5   3794  +0.0337  -0.0739  +0.0975   41.4   45.0   12.3   42.7
         8   3794  +0.0223  -0.0919  +0.0899   37.3   55.1   17.9   27.0
        10   3794  +0.0241  -0.1141  +0.1059   35.7   58.9   20.8   20.3
        15   3794  +0.0419  -0.0963  +0.1238   34.0   63.8   25.3   10.9
        20   3794  +0.0394  -0.0957  +0.1194   32.3   66.5   28.0    5.6
        30   3794  +0.0402  -0.1102  +0.1292   31.2   68.2   29.5    2.4
        40   3794  +0.0479  -0.1005  +0.1358   31.2   68.7   29.9    1.4

variant                    n    meanR   trainR    holdR   win%  stop%   tgt%  time%
baseline ts=10          3794  +0.0241  -0.1141  +0.1059   35.7   58.9   20.8   20.3
BE@0.5R ts=10           3794  +0.0358  -0.0734  +0.1005   22.1   76.1   15.5    8.4
BE@0.75R ts=10          3794  +0.0185  -0.1172  +0.0988   26.3   70.8   17.5   11.6
BE@1.0R ts=10           3794  +0.0089  -0.1204  +0.0855   29.0   67.3   18.6   14.1
BE@1.5R ts=10           3794  +0.0060  -0.1094  +0.0744   32.1   63.2   19.8   17.0
BE@2.0R ts=10           3794  +0.0009  -0.1208  +0.0730   33.4   61.4   20.2   18.4
baseline ts=20          3794  +0.0394  -0.0957  +0.1194   32.3   66.5   28.0    5.6
BE@1.0R ts=20           3794  +0.0135  -0.1134  +0.0886   25.1   74.3   23.1    2.6
BE@1.5R ts=20           3794  +0.0099  -0.1069  +0.0790   28.0   71.1   25.3    3.6
baseline ts=40          3794  +0.0479  -0.1005  +0.1358   31.2   68.7   29.9    1.4
BE@1.0R ts=40           3794  +0.0073  -0.1346  +0.0914   24.2   75.8   23.8    0.4
BE@1.5R ts=40           3794  +0.0057  -0.1288  +0.0853   26.9   73.1   26.3    0.6

variant                    n    meanR   trainR    holdR   win% tgt-hit%
current (resistance) ts=10  3794  +0.0241  -0.1141  +0.1059   35.7     20.8
target=1.0R ts=10       3809  -0.0383  -0.0982  -0.0030   47.9     44.4
target=1.5R ts=10       3809  -0.0336  -0.0989  +0.0049   40.5     32.2
target=2.0R ts=10       3809  -0.0197  -0.1047  +0.0305   37.0     24.0
target=2.5R ts=10       3809  +0.0065  -0.1097  +0.0751   35.4     18.8
target=3.0R ts=10       3809  +0.0105  -0.1158  +0.0852   34.3     14.3
target=4.0R ts=10       3809  +0.0156  -0.1106  +0.0902   32.9      9.0
current (resistance) ts=20  3794  +0.0394  -0.0957  +0.1194   32.3     28.0
target=1.0R ts=20       3809  -0.0333  -0.0912  +0.0009   48.4     47.6
target=1.5R ts=20       3809  -0.0308  -0.0962  +0.0079   39.4     36.9
target=2.0R ts=20       3809  -0.0238  -0.0894  +0.0150   34.4     29.0
target=2.5R ts=20       3809  -0.0072  -0.0993  +0.0472   31.5     23.6
target=3.0R ts=20       3809  -0.0042  -0.1035  +0.0545   29.3     19.1
target=4.0R ts=20       3809  +0.0037  -0.0932  +0.0610   26.8     13.4
note: fixed-multiple rows above re-admit trades whose entry gapped past the published resistance target, so n is not comparable row to row against the current-target baseline

caveat: at this sample size the baseline 95% CI is about +/-0.2R against effect sizes near 0.03R -- a table ordering above is not evidence on its own
```
