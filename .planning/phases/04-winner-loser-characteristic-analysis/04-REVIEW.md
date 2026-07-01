---
phase: 04-winner-loser-characteristic-analysis
reviewed: 2026-07-01T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - scanner/backtest.py
  - scanner/report.py
  - scanner/simulate.py
  - tests/test_report.py
  - web/api/routes/runs.js
  - web/ui/src/app/pages/backtests/backtests.component.html
  - web/ui/src/app/pages/backtests/backtests.component.spec.ts
  - web/ui/src/app/pages/backtests/backtests.component.ts
  - web/ui/src/app/services/api.service.ts
findings:
  critical: 2
  warning: 9
  info: 1
  total: 12
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-07-01
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

This phase adds winner/loser characteristic analysis (W/L analysis), surfaces six pre-registered entry-time metrics through the backtest pipeline, and wires them into the Express API and Angular UI. The design contract (WLA-01 through WLA-06) is solid and consistently enforced in both Python and TypeScript. The core simulation logic in `simulate.py` is correct. Two blockers require a fix before this ships: an uncaught `JSON.parse` in the Express route that will crash the server on DB corruption, and a signal-key collision in the trade list that produces wrong stop/target values for `strategy=both` backtest reports. Nine warnings cover silent exception swallowing, a hot-loop import, a NaN-to-bool coercion, a race condition in the UI, and several minor reporting inconsistencies.

---

## Critical Issues

### CR-01: `JSON.parse` without try/catch crashes the runs route on corrupt DB data

**File:** `web/api/routes/runs.js:44` (also line 60)

**Issue:** Both `JSON.parse(report.metrics_json || '{}')` (line 44) and `JSON.parse(report.biases_json || '[]')` (line 60) are unguarded. If either column contains truncated or malformed JSON — which can happen after an interrupted write, disk error, or schema migration — `JSON.parse` throws a `SyntaxError`. In Express, an uncaught synchronous throw inside a route handler propagates to the default error handler and returns HTTP 500 with no structured JSON body. The Angular client's `catchError(() => of(null))` absorbs the HTTP error, but the server process logs a stack trace and the route is effectively down until restart.

**Fix:**
```javascript
// wrap both parse calls in a helper
function safeParse(json, fallback) {
  try { return JSON.parse(json); } catch { return fallback; }
}

// line 44
const reportData = safeParse(report.metrics_json, {});

// line 60
result.biases = safeParse(report.biases_json, []);
```

---

### CR-02: 2-tuple signal key in `render_report` trade list drops strategy dimension — wrong stop/target for `strategy=both` runs

**File:** `scanner/report.py:778`

**Issue:** `render_report` builds its lookup dict for the trade list as:
```python
sig_by_key = {(str(s.date), s.ticker): s for s in signals}
```
This is a 2-tuple key `(date, ticker)`. When a backtest is run with `strategy=both`, the same ticker can produce both a pullback signal and a breakout signal on the same date. Each signal carries different `stop` and `target` values. The dict comprehension silently clobbers one signal with the other (last writer wins), so one of the two strategies' trades will display wrong stop/target values in the JSON trade list and the UI.

The W/L analysis helper (line 149) correctly uses a 3-tuple `(str(s.date), s.ticker, s.strategy)` and is not affected.

**Fix:**
```python
# line 778 — add strategy as the third key dimension
sig_by_key = {(str(s.date), s.ticker, s.strategy): s for s in signals}

# line 783 — update the lookup to match
sig = sig_by_key.get((str(t.signal_date), t.ticker, t.strategy))
```

---

## Warnings

### WR-01: Silent `except Exception: pass` discards programming errors in signal generation

**File:** `scanner/backtest.py:374-378` and `scanner/backtest.py:423-424`

**Issue:** Two separate bare `except Exception: pass` blocks swallow all exceptions from `_targets.attach_risk` (lines 374-378) and from the entire `compute_confidence` block (lines 385-424). Any unhandled bug in those functions — wrong attribute access, a shape mismatch, a logic regression — is silently eaten and the signal is either dropped (if stop/target is None) or emitted with a default confidence. Debugging a regressed backtest run becomes very difficult because the error signal is lost.

**Fix:** At minimum, log the exception at WARNING level before continuing so errors are visible in the run output:
```python
except Exception as exc:
    _log.warning("attach_risk failed for %s on %s: %r", ticker, d, exc)
    pass
```
Apply the same pattern to the confidence block. This preserves the "never crash a full backtest run" property while making regressions detectable.

---

### WR-02: `import pandas as _pd` inside the per-day hot loop

**File:** `scanner/backtest.py:337`

**Issue:** The statement `import pandas as _pd` appears inside `for day_num, d in enumerate(trading_days)`, which executes once per trading day. Python's import system caches modules after the first import, so subsequent calls are a dictionary lookup rather than a full load. However, this is still executed on every iteration and is confusing — imports belong at the top of the function or module. If the trading date range spans 1 000 days, Python performs 1 000 redundant import-cache lookups.

**Fix:** Move `import pandas as _pd` (and the matching `import pandas as _pd` alias) to the top of `generate_signals`, alongside the other lazy imports already hoisted there. Alternatively, since `pd` is already imported at module level as `import pandas as pd`, replace all `_pd.` references inside the loop with `pd.`.

---

### WR-03: `bool(NaN)` evaluates to `True` — MACD bullish incorrectly True for early dates

**File:** `scanner/backtest.py:406`

**Issue:**
```python
macd_val = bool(precomp_t.macd_bullish.asof(as_of_ts))
```
`precomp_t.macd_bullish` is filled with `False` for `NaN` positions via `.fillna(False)` (line 112). However, `pd.Series.asof(ts)` returns `NaN` when `ts` is before the first index entry — i.e., for the earliest dates in the backtest range before the MACD warm-up window is complete. `bool(float('nan'))` evaluates to `True` in Python (NaN is non-zero), so every signal generated before enough MACD history exists is treated as "MACD bullish" regardless of actual price action. This inflates confidence scores for early-period signals.

**Fix:**
```python
_raw_macd = precomp_t.macd_bullish.asof(as_of_ts)
macd_val = bool(_raw_macd) if not pd.isna(_raw_macd) else False
```

---

### WR-04: Race condition in `selectRun` — concurrent requests, last response wins

**File:** `web/ui/src/app/pages/backtests/backtests.component.ts:31-37`

**Issue:**
```typescript
selectRun(runId: string): void {
  this.detailLoading = true;
  this.router.navigate(['/backtests', runId]);
  this.api.getRun(runId).subscribe(r => {
    this.selectedRun = r;
    this.detailLoading = false;
  });
}
```
There is no unsubscription or cancellation of a pending `getRun` call. If the user clicks Run A and then quickly clicks Run B, both HTTP requests are in flight simultaneously. Whichever response arrives last sets `selectedRun`, which may display Run A's data under the URL for Run B. Large run reports (many trades) are slow to return; the race is realistic.

**Fix:** Use `switchMap` to cancel the in-flight request when a new run is selected:
```typescript
private selectedRunId$ = new Subject<string>();

ngOnInit(): void {
  this.selectedRunId$.pipe(
    switchMap(id => this.api.getRun(id))
  ).subscribe(r => {
    this.selectedRun = r;
    this.detailLoading = false;
  });
  // ...
}

selectRun(runId: string): void {
  this.detailLoading = true;
  this.router.navigate(['/backtests', runId]);
  this.selectedRunId$.next(runId);
}
```

---

### WR-05: No user-visible error when `getRun` fails — shows misleading "Select a run" prompt

**File:** `web/ui/src/app/pages/backtests/backtests.component.ts:34-37`

**Issue:** `this.api.getRun(runId)` uses `catchError(() => of(null))`, so API failures silently return `null`. The component sets `this.selectedRun = null` and `this.detailLoading = false`, which causes the template to render the "Select a run on the left to view its report" empty-state message. The user cannot distinguish between "no run selected yet" and "the selected run failed to load."

**Fix:** Add an `error` flag and a corresponding error message in the template:
```typescript
this.api.getRun(runId).subscribe(r => {
  this.selectedRun = r;
  this.detailLoading = false;
  this.runLoadError = r === null; // show error if null returned
});
```

---

### WR-06: W/L delta column in markdown report reuses value formatter — wrong unit suffix on RVOL delta

**File:** `scanner/report.py:734`

**Issue:**
```python
d_fmt = _fmt_wl_value(row['metric'], row['delta'])
```
`_fmt_wl_value` was designed to format absolute metric values. Reusing it for the delta column produces misleading output:
- For `RVOL`, a delta of `+0.23` is formatted as `"0.23x"`. The `x` suffix implies a ratio multiplier; applied to a difference it is semantically wrong.
- For `RSI at entry`, `ATR multiple`, and `Pct to 52w high`, positive deltas are rendered without a leading `+` sign, inconsistent with the Angular UI's `fmtWlDelta` which always prepends `+` to non-negative deltas (verified in `backtests.component.spec.ts` lines 103-133).

**Fix:** Extract a dedicated delta formatter:
```python
def _fmt_wl_delta(metric: str, v: Optional[float]) -> str:
    if v is None:
        return "—"
    sign = '+' if v >= 0 else ''
    if metric == 'RSI at entry':
        return f"{sign}{v:.1f}"
    if metric == 'RVOL':
        return f"{sign}{v:.2f}"    # no 'x' suffix on a difference
    if metric in ('Pullback depth %', 'Industry momentum', 'Pct to 52w high'):
        return f"{sign}{v:.1f}%"
    if metric == 'ATR multiple':
        return f"{sign}{v:.2f}"
    return f"{sign}{v:.2f}"

# line 734 — replace _fmt_wl_value with the new formatter
d_fmt = _fmt_wl_delta(row['metric'], row['delta'])
```

---

### WR-07: `median_holding_days` uses upper-median for even-length lists, inconsistent with `_safe_median`

**File:** `scanner/report.py:239`

**Issue:**
```python
median_hold = holding[len(holding) // 2] if holding else None
```
For an even-length list `[5, 7, 9, 12]`, `n//2 = 2`, so `holding[2] = 9` is returned. The conventional median would be `(7 + 9) / 2 = 8.0`. `_safe_median` in the same file correctly averages the two middle values (lines 65-68). The two median implementations are inconsistent.

While `holding_days` values are integers and the off-by-one direction is predictable (always rounds up), this may produce a slightly optimistic holding-days figure.

**Fix:** Either reuse `_safe_median`:
```python
median_hold = _safe_median(list(holding)) if holding else None
```
or average the two central elements:
```python
n = len(holding)
median_hold = holding[n // 2] if n % 2 == 1 else (holding[n // 2 - 1] + holding[n // 2]) / 2 if n else None
```

---

### WR-08: `_is_breakout_result` detected via unrelated `vol_ratio` attribute instead of `isinstance`

**File:** `scanner/backtest.py:435`

**Issue:**
```python
_is_breakout_result = getattr(result, 'vol_ratio', None) is not None
```
This heuristic conflates two independent facts: (a) is this a `BreakoutResult`? and (b) does this particular breakout have a valid volume ratio? If a `BreakoutResult` has `vol_ratio=None` due to a data gap, `_is_breakout_result` is `False` and the code falls through to the pullback path for `pct_to_52w_high`. In this case both paths happen to compute the same value (% below 52w high) by different routes, so the end result is numerically identical. However, the code's stated intent is to detect the result type, and using an optional payload field for type dispatch is fragile and will silently misbehave if the attribute set of either strategy type changes.

**Fix:**
```python
from scanner.strategies.breakout import BreakoutResult
_is_breakout_result = isinstance(result, BreakoutResult)
```
(`PullbackResult` is already imported nearby on line 395.)

---

### WR-09: `earn_skip_pct` label and report text describe the wrong quantity

**File:** `scanner/report.py:759-765`

**Issue:**
```python
earn_skip_n = sum(
    1 for t in all_trades
    if "Earnings clear" in (t.failed_gates or [])
)
earn_skip_pct = earn_skip_n / len(signals) if signals else 0.0
...
f"**Earnings gate skip rate** — {earn_skip_pct:.1%} of signals had no earnings "
"data and were evaluated without the earnings-proximity gate."
```
"Earnings clear" appearing in `failed_gates` means the earnings gate was active and **failed** — the trade was within 7 days of an earnings event. Skipped gates (no data available) do not add "Earnings clear" to `failed_gates`; they are silent passes. So `earn_skip_n` counts gate **failures**, not skips. The variable name and report text both incorrectly say "skip rate" and "had no earnings data", when the opposite is true: these signals had earnings data and were close to an event.

**Fix:** Rename the variable to `earn_fail_n` and correct the report text:
```python
earn_fail_n = sum(
    1 for t in all_trades
    if "Earnings clear" in (t.failed_gates or [])
)
earn_fail_pct = earn_fail_n / len(signals) if signals else 0.0
...
f"**Earnings gate block rate** — {earn_fail_pct:.1%} of signals were within "
"the 7-day earnings buffer and failed the earnings-proximity gate."
```

---

## Info

### IN-01: Unused import `_attach_industry_rank_pct` in `backtest.py`

**File:** `scanner/backtest.py:23`

**Issue:**
```python
from scanner.core import (
    ...
    _attach_industry_rank_pct,
)
```
`_attach_industry_rank_pct` is imported but never called anywhere in `backtest.py`. The rank percentile is computed inline (lines 338-339) and the result is assigned directly to `_rank_pct` at line 432 without calling this helper.

**Fix:** Remove `_attach_industry_rank_pct` from the import.

---

_Reviewed: 2026-07-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
