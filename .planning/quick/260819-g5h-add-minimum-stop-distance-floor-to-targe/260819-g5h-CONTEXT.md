# Quick Task 260819-g5h: Add minimum stop distance floor to targets.py stop engine - Context

**Gathered:** 2026-08-19
**Status:** Ready for planning

<domain>
## Task Boundary

Add a minimum stop-distance floor to the stop/target engine in `scanner/targets.py`.

**CHANGES TRADING LOGIC** — explicitly approved by István on 2026-08-19, backed by the
backtest evidence below. This is the "explicit task backed by data" that CLAUDE.md requires
before altering stop rules.

### Problem

The pullback stop (`EMA20 − ATR`) and breakout stop (`high20 − 0.5×ATR`) have no minimum
distance from entry. When price closes just above the computed stop level, risk-per-share
collapses toward zero. That produces unexecutable trades and corrupts every R-multiple
metric downstream (`r_multiple`, `target_r`, `mae_r`, `mfe_r`, and the risk-based sizing
formula).

### Evidence

Backtest run `4f4fe68_2021-01-01_20260702_090418` (pullback, sp600, 2021-01 → 2026-06,
3,813 qualified resolved trades):

- 15 trades have `|r_multiple| > 10`; 338 have `target_r > 10`; max `target_r` = 4,128,767
- Worst cases:
  - EPAC 2024-01-16 — entry 28.91 / stop 28.89 = **2.4 cents** risk vs ATR 0.71 (0.03×ATR) → 72.7R
  - GNW 2025-07-16 — entry 7.30 / stop 7.29 = **1.0 cent** risk vs ATR 0.20 (0.05×ATR) → 50.0R
- Those 15 trades flip the strategy's sign: raw mean R = +0.051, winsorized at ±10R = −0.007,
  winsorized at ±5R = −0.057
- Sizing is `floor((account × risk%) / (entry − stop))`, so EPAC at 1% risk on a $50k account
  asks for 20,833 shares = $602k of stock — unexecutable

### Stop-distance distribution (same run, stop distance ÷ ATR)

| percentile | p01 | p05 | p10 | p25 | p50 | p75 | p90 |
|---|---|---|---|---|---|---|---|
| stop/ATR | 0.055 | 0.182 | 0.322 | 0.610 | 0.986 | 1.391 | 1.720 |

### Measured impact of candidate floors

| Floor | Signals affected | mean R if dropped | mean R if widened* |
|---|---|---|---|
| 0.25×ATR | 290 (7.6%) | +0.017 | +0.025 |
| 0.35×ATR | 430 (11.3%) | +0.003 | +0.021 |
| **0.50×ATR** | **713 (18.7%)** | −0.001 | **+0.014** |
| 0.75×ATR | 1,290 (33.8%) | −0.033 | +0.005 |

Baseline with no floor: +0.051.

\* The "widened" column rescales R by (actual stop distance ÷ floored stop distance) while
holding the exit path fixed. It therefore **understates** widening — a genuinely wider stop
would also survive some exits that currently stop out. Only a re-simulation gives the true
number. Do not treat +0.014 as a prediction.

</domain>

<decisions>
## Implementation Decisions

### Floor multiplier — LOCKED: 0.5×ATR

The floor is `0.5 × ATR`. Chosen on execution-realism grounds, not by maximizing backtest
expectancy — deliberately so. The breakout stop rule already uses a 0.5×ATR buffer, which
makes this a consistent house rule rather than a constant fitted to this one backtest.
A stop placed inside half an ATR cannot survive normal intraday noise.

Do NOT tune this multiplier to improve measured expectancy. Selecting it on the same data
that motivated the fix is precisely the overfitting failure this project has already
recorded (see PROJECT.md, ADX / volume-contraction gate removal).

### Behavior when the strategy stop falls inside the floor — LOCKED: widen

`stop = min(strategy_stop, entry − 0.5 × ATR)`

The stop may only ever move **further** from entry, never closer. Rationale: the setup
itself is still valid — only the stop placement was degenerate — so keep the trade with an
honest, larger risk-per-share and a correspondingly smaller R. This preserves sample size
and matches what a human trader would do. Signals are NOT dropped.

### Scope — both strategies

Applies to the pullback stop rule and the breakout stop rule alike. Both are computed in
`scanner/targets.py`.

### Claude's Discretion

- Exact placement within `targets.py` (inside the per-strategy stop helpers vs. a single
  shared clamp applied in `attach_risk`). A single shared clamp is preferred if it does not
  complicate the existing structure — one place to reason about beats two.
- Whether to expose the multiplier as a module-level named constant (e.g. `MIN_STOP_ATR_MULT
  = 0.5`) — recommended for discoverability, consistent with existing constants in `core.py`.
- Unit-test structure and fixture choice.
- Whether to record a flag on widened signals was offered and NOT selected — do not add
  schema or DB-write changes for this task.

</decisions>

<specifics>
## Specific Ideas

### Guardrails (from CLAUDE.md, non-negotiable)

- `pytest -q` must stay green.
- Do NOT change gate thresholds or score formulas — this task touches stop placement only.
- No `datetime.now()` / `pd.Timestamp.now()` in evaluation logic — use `ctx.as_of`.
- No `yf.` imports outside `data_store.py` / `earnings_store.py`.

### Golden-master fixtures

`tests/golden/pullback_qualifying.json`, `tests/golden/pullback_near_miss.json`, and
`tests/golden/breakout_qualifying.json` are consumed by `tests/test_golden_master.py` and
very likely encode stop/target values that this change shifts.

**FLAG, do not silently regenerate.** If fixtures need updating, surface exactly which
values changed and why in the SUMMARY, and regenerate only after confirming the deltas are
explained by the floor and nothing else. A silently rewritten golden master destroys the
regression signal it exists to provide.

### Guard against degenerate inputs

The floor must behave sensibly when ATR is 0, NaN, or None — do not produce a stop equal to
or above entry, and do not raise. Existing callers already wrap `attach_risk` in a
`try/except (ValueError, AttributeError, KeyError, IndexError)` (see
`scanner/backtest.py:374`), so a silent exception would drop signals invisibly.

### Not in scope

- Re-running the backtest (a separate follow-up; the run is ~2.9h for 3 years on sp600)
- Persisting `rsi_entry` / `rvol` / `pullback_depth_pct` / `pct_to_52w_high` to the `signals`
  table (a separate known gap in `store_db.py`)
- Any change to gate logic, scoring, or confidence

</specifics>

<canonical_refs>
## Canonical References

- `CLAUDE.md` — "Key design decisions": stop rules are Pullback `EMA20−ATR`, Breakout
  `high20−0.5×ATR`; gate thresholds and score formulas are not to be changed without an
  explicit task
- `.planning/PROJECT.md` — gate-stability constraint; the ADX / volume-contraction removal
  precedent for not fitting constants to a single backtest
- `scanner/targets.py` — the stop/target engine and `attach_risk`
- `scanner/backtest.py:374` — `attach_risk` call site wrapped in a broad `except`
- `tests/golden/` + `tests/test_golden_master.py` — fixtures at risk

</canonical_refs>
