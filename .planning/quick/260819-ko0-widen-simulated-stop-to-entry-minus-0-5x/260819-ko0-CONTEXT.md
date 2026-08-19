# Quick Task 260819-ko0: Entry-side stop floor in simulate.py - Context

**Gathered:** 2026-08-19
**Status:** Ready for planning

<domain>
## Task Boundary

Apply the 0.5x ATR minimum-risk floor at **entry** as well as at signal close.

**CHANGES TRADING LOGIC** — approved by Istvan 2026-08-19, backed by the measured evidence
below. This is the second half of quick task 260819-g5h, which fixed only the close side.

### Problem

`scanner/targets.py` (quick task 260819-g5h) floors the stop so that
`close - stop >= 0.5 x ATR`. That makes the *published* stop executable at signal time.

But `scanner/simulate.py:160` computes `risk = entry_px - sig.stop`, and entry is the NEXT
OPEN (`--entry next_open`). An adverse overnight gap shrinks the real risk denominator again,
and the close-side floor makes this WORSE in one specific way: it pins an entire population at
exactly 0.5x ATR, so any negative gap at all pushes them under.

Measured on backtest run `038a385_2021-01-01_20260819_142048` (pullback, sp600,
2021-01-01 to 2026-06-30, 3,820 qualified+resolved trades):

- CLOSE-based stop/ATR: min **0.5000** — the close-side floor works exactly as specified
- ENTRY-based stop/ATR: min **0.0028**, with **551 trades (14.4%)** below 0.5
- max R is still **56.0**; 11 trades still have `|R| > 10`
- raw mean R +0.064 but winsorized at +-5R it is **-0.010** — the sign still flips, which was
  the original diagnostic that the edge was an artifact

### It manufactures false discoveries

This is not merely cosmetic. Running the winner/loser analysis on this run produced exactly
one rule whose holdout CI excluded zero: `rsi_entry < 48.2`, holdout mean R **+0.580**,
CI [+0.053, +1.098]. It looked like a shippable gate.

It is an artifact. Low RSI means a deeper pullback, which puts price near `EMA20 - ATR`, which
is precisely when the close-side floor binds:

| | `rsi < 48.2` | `rsi >= 48.2` |
|---|---|---|
| pinned exactly at the 0.5x ATR floor | **78.1%** | 3.0% |
| entry-based risk below 0.5x ATR | **38.9%** | 7.4% |
| mean R raw | +0.580 | +0.059 |
| winsorized +-2R | **-0.197** | -0.082 |

The rule does not select profitable trades. It selects trades whose R is mismeasured. Until
this is fixed, the analysis pipeline that informs gate decisions will keep producing
significant-looking results driven by collapsed denominators.

</domain>

<decisions>
## Implementation Decisions

### LOCKED: widen the stop, do not skip the trade

`effective_stop = min(sig.stop, entry_px - 0.5 * ATR)`

Applied in `scanner/simulate.py` at the point the trade is set up, before risk is computed.
The stop may only move FURTHER from entry, never closer.

Chosen over skipping on the evidence. The 551 affected trades are 82.9% losers (457 losers,
94 winners; stop-out rate 82.6% vs 55.6% for the rest) — but measured on a corrected risk
basis they score **+0.152 mean R against +0.014 for the trades that would be kept**, with the
top rescaled outcomes clustered at 9.2 / 6.7 / 6.7 / 6.3 / 6.3 rather than one freak. Skipping
would remove the losers AND the fat right tail that pays for them. Istvan's decision: "94
winning trades is a fair share of actual winners, so let's see how it performs when I widen
the stop."

### CRITICAL: this must be a REAL stop change, not just a denominator change

`sig.stop` is used for far more than the risk denominator in `simulate_trades`:

- stop-hit detection — `stop_hit = low <= sig.stop` (~line 188)
- exit price on a stop-out — `exit_px_val = sig.stop` (~line 193)
- the post-stop shadow calculation (~lines 197-204)
- `mae_r` / `mfe_r`, which divide by `risk`

**Every one of these must use the widened effective stop.** Computing R against a wider stop
while still exiting at the tighter one would produce a fake improvement — the change would
look like it worked while measuring something that never happened. This is the single highest
risk in the task.

### LOCKED: the gap_skip_down guard is unchanged

`simulate.py:149` currently skips the trade when `entry_px <= sig.stop` (exit reason
`gap_skip_down`). That guard MUST continue to be evaluated against the **original** signal
stop, before any widening. If the open is at or below the planned stop, the setup is broken
and the trade is still skipped.

Widening applies only where `entry_px > sig.stop` AND the gap left less than 0.5x ATR of room.
The measured 551 are all in that band (they have non-NULL `r_multiple`, so they were never
gap-skipped). Letting the widened stop rescue a `gap_skip_down` trade into a tradeable one
would be an unintended scope expansion — the same class of bug the guard-order decision in
260819-g5h existed to prevent.

`gap_skip_up` (`entry_px >= sig.target`) is likewise unchanged.

### LOCKED: no schema change, no new column

Recording the adjustment was offered and declined. Do not bump `schema_version`, do not add
columns, do not touch `store_db.py`.

**Documented consequence:** the `signals.stop` column keeps the published close-based stop,
while a stop-out's `exit_px` will now be the widened effective stop. For the affected ~14% of
trades those two values will differ, and `(entry_px - stop) / atr` computed from DB columns
will still read below 0.5 even though the trade used a wider stop. This is expected, not a
bug — but it WILL confuse anyone recomputing risk from the columns later. It must be called
out explicitly in the SUMMARY and in the `CLAUDE.md` note about the stop rules.

### Claude's Discretion

- Where exactly in `simulate_trades` the effective stop is computed, and whether it is
  extracted into a small named helper (a helper is preferred for testability, mirroring
  `apply_min_stop_floor` in `targets.py`).
- Whether to reuse `MIN_STOP_ATR_MULT` from `scanner/targets.py` rather than redefining 0.5.
  Reuse is strongly preferred — one constant, one house rule. Verify no circular import.
- Test structure.

</decisions>

<specifics>
## Specific Ideas

### Degenerate inputs

`Signal.atr` is a plain `float` (simulate.py:25) and backtest.py populates it as
`result.atr or 0.0`, so **ATR can legitimately be 0.0**. When ATR is 0, non-finite, or the
computed floor would not sit strictly below `entry_px`, leave the stop unchanged — the
existing `entry_px > sig.stop` guard already established the stop is below entry, so the
original value stays valid. Never raise, and never emit a stop at or above entry.

### Expected outcome (sanity targets, not acceptance criteria)

Rescaling the 551 affected trades to a 0.5x ATR basis predicts, for the full run:

- max R drops from 56.0 to roughly 9
- `|R| > 10` count drops to ~0
- raw mean R and winsorized mean R **converge** (approximately +0.034 raw vs +0.024 at +-5R,
  versus +0.064 / -0.010 today). That convergence is the real success signal — it means the
  average is no longer carried by collapsed denominators.

These are approximations from rescaling with the exit path held fixed. The true numbers should
be **better**, because a genuinely wider stop will rescue some of the 455 stop-outs in that
group. If the actual result comes out materially WORSE than these targets, something is wrong
— investigate rather than accepting it.

Do NOT tune the 0.5 multiplier to hit these numbers.

### Guardrails (CLAUDE.md, non-negotiable)

- `pytest -q` must stay green (currently 388 passing)
- Do NOT change gate thresholds or score formulas
- No `datetime.now()` / `pd.Timestamp.now()` in evaluation logic
- No `yf.` imports outside data_store.py / earnings_store.py
- Tests must pass offline; do not depend on `data/scanner.db`

### Existing tests at risk

`tests/` has simulate coverage that pins stop-out exit prices and R values. Any fixture whose
entry gaps into the sub-0.5x ATR band will legitimately change. **Enumerate every changed
expectation with before/after and cause in the SUMMARY — never silently rewrite one.** If a
test that should NOT be affected starts failing, the implementation is wrong; fix the code.

### Not in scope

- Re-running the backtest (the user will decide; the existing run
  `038a385_2021-01-01_20260819_142048` becomes stale on merge)
- Any change to `targets.py` — the close-side floor stays exactly as shipped
- Any change to gate logic, scoring, or confidence
- Web/UI changes

</specifics>

<canonical_refs>
## Canonical References

- `scanner/simulate.py:134-204` — entry, gap guards, risk, stop-hit, exit, post-stop shadow
- `scanner/simulate.py:15-38` — the `Signal` dataclass (`stop`, `target`, `atr`)
- `scanner/targets.py` — `MIN_STOP_ATR_MULT`, `apply_min_stop_floor` (the close-side floor,
  quick task 260819-g5h) — the pattern to mirror
- `.planning/quick/260819-g5h-add-minimum-stop-distance-floor-to-targe/` — the close-side
  half of this fix, including the guard-order lesson
- `CLAUDE.md` — stop rules table; gate-stability rule

</canonical_refs>
