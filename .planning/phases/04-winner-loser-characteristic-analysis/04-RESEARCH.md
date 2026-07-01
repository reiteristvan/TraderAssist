# Phase 4: Winner/Loser Characteristic Analysis - Research

**Researched:** 2026-07-01
**Domain:** Python backtest reporting + Angular web UI extension
**Confidence:** HIGH

---

## Summary

Phase 4 delivers a pre-registered winner/loser (W/L) characteristic analysis inside the backtest report. The analysis compares median values of six entry-time metrics across winners vs losers, separately by strategy, with hard guards against both small-sample spurious findings and post-hoc feature selection.

The core technical challenge is that four of the six metrics (RSI at entry, RVOL, pullback depth %, pct to 52w high) are computed inside strategy `evaluate()` functions but are NOT currently transferred to the `Signal` dataclass. Phases 1-3 established the precedent: add optional fields to Signal with `None` defaults. Phase 4 follows that exact pattern for four more fields. No DB schema bump is required — the W/L analysis is computed in memory during `render_report()` and stored in `backtest_reports.metrics_json` as a `wl_analysis` key.

The web surface is fully specified in `04-UI-SPEC.md` (already approved). All CSS classes, copy, color values, and JSON shapes are pre-decided; the planner and executer should treat that spec as locked.

**Primary recommendation:** Extend Signal with four optional metric fields, populate them in `backtest.py:generate_signals()`, then add `WL_FEATURES` + `wl_characteristic_analysis()` to `report.py`, followed by API and Angular wire-up. Two plans — Python backend then web — with the second plan gated on the first.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WLA-01 | Backtest reports include a W/L characteristic analysis section showing median entry-time metric values for winners vs losers | `wl_characteristic_analysis()` function added to report.py; median values computed via `_safe_median()` helper |
| WLA-02 | Analysis covers at minimum 6 entry metrics: RSI at entry, RVOL, pullback depth %, ATR multiple, industry momentum, pct to 52w high | `WL_FEATURES` constant pre-registers exactly these 6 metrics in report.py source code |
| WLA-03 | Analysis produced separately for pullback and breakout strategies, not combined | `wl_characteristic_analysis()` groups by `Trade.strategy`; produces one strategy dict per strategy present in the run |
| WLA-04 | Industry momentum included as one discriminating dimension | `Signal.industry_momentum` already exists; included as 5th entry in WL_FEATURES |
| WLA-05 | Cell-size gate: bucket with fewer than 50 trades shows warning, not medians | `WL_MIN_BUCKET = 50` constant; strategy entry sets `suppressed: True` with copy in `suppression_reason` |
| WLA-06 | Feature list pre-registered in code (fixed list, not exploratory) to prevent multiple-comparisons overfitting | `WL_FEATURES` is a module-level constant committed before any backtest run |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

- No `yf.` imports outside `data_store.py` / `earnings_store.py` — Phase 4 has zero yfinance calls
- No `datetime.now()` inside evaluation logic — W/L analysis only reads from Signal/Trade objects, no wall clock
- Do not change gate thresholds or score formulas — W/L analysis is display-only, never a gate
- `pytest -q` must stay green after every Python change
- `npm test` (API) and `ng test` (UI) must stay green after web changes
- New display fields flow through the same signal pipeline (scanner → DB → API → UI)
- No new DB tables without schema version bump — W/L analysis is stored in existing `backtest_reports.metrics_json` blob; no schema change required

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Metric extraction (RSI, RVOL, pullback depth, pct to 52w high) | Backend — backtest.py | Backend — signal generation loop | Computed from pre-computed indicator series at signal time; no live prices |
| W/L median computation + sample-size gates | Backend — report.py | — | Pure in-memory analytics over qualified trades; no I/O |
| Pre-registration constant (WL_FEATURES) | Backend — report.py source | — | Must live in source code as a constant, not in a config or DB |
| JSON serialization of wl_analysis | Backend — report.py + runs.js | — | report.py writes to json_out; runs.js exposes from metrics_json |
| W/L display (cards, table, warnings) | Frontend — Angular | — | Reads wl_analysis from API; renders per 04-UI-SPEC.md |

---

## Standard Stack

### Core (all already installed — no new packages)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| Python stdlib `statistics` OR sorted-list midpoint | stdlib | Median computation | No import needed if using sorted list approach |
| pandas | already installed | Optional: `pd.Series.median()` | Already used in report.py |
| Angular built-in | already installed | W/L card template + formatting | Detected from backtests.component |

**Installation:** No new packages. Zero `npm install` or `pip install` needed.

**Version verification:** N/A — all computation uses existing stdlib + already-installed libraries.

---

## Package Legitimacy Audit

> No new external packages are introduced in Phase 4.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | N/A |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious:** none

---

## Architecture Patterns

### System Architecture Diagram

```
backtest.py:generate_signals()
  ├─ pb.evaluate() → PullbackResult { rsi, pullback_depth_pct, ... }
  │   └─ Signal { ..., rsi_entry=rsi, rvol=computed_from_precomp,
  │               pullback_depth_pct=depth, pct_to_52w_high=computed }
  └─ br.evaluate() → BreakoutResult { rsi, vol_ratio, pct_to_52w_high, ... }
      └─ Signal { ..., rsi_entry=rsi, rvol=vol_ratio,
                  pullback_depth_pct=None, pct_to_52w_high=pct }

scan.py:cmd_backtest()
  ├─ signals = generate_signals(...)          # list[Signal] with all 4 new fields
  ├─ q_trades = simulate_trades(q_signals)   # Trade.target_atr populated
  └─ md, json_out = render_report(signals, q_trades, ...)
                       │
                       ├─ wl = wl_characteristic_analysis(signals, q_trades)
                       │         ├─ sample-size gate (total < 200 → abort)
                       │         ├─ per-strategy split (by Trade.strategy)
                       │         ├─ per-strategy gate (bucket < 50 → suppress)
                       │         └─ median per WL_FEATURES metric
                       └─ json_out['wl_analysis'] = wl  ──► backtest_reports.metrics_json

API: GET /api/runs/:run_id
  └─ reportData = JSON.parse(metrics_json)
     result.wl_analysis = reportData.wl_analysis || null  ──► Angular

Angular: backtests.component
  ├─ wlAnalysis getter → WlAnalysis | null
  ├─ abort guard → single .warning-box
  └─ per-strategy .card → [6-row table] or [suppression .warning-box]
```

### Recommended Project Structure

```
scanner/
  simulate.py        # ADD: rsi_entry, rvol, pullback_depth_pct, pct_to_52w_high to Signal
  backtest.py        # ADD: populate 4 new Signal fields in generate_signals() inner loop
  report.py          # ADD: WL_FEATURES, WL_MIN_TOTAL, WL_MIN_BUCKET,
                     #       wl_characteristic_analysis(), _extract_metric(), _safe_median()
                     #       EXTEND: render_report() to call analysis + emit markdown section
web/api/routes/
  runs.js            # ADD: result.wl_analysis = reportData.wl_analysis || null
web/ui/src/app/
  services/
    api.service.ts   # ADD: WlMetricRow, WlStrategyAnalysis, WlAnalysis interfaces;
                     #       wl_analysis field to Run interface
  pages/backtests/
    backtests.component.ts   # ADD: wlAnalysis getter, fmtWlValue(), fmtWlDelta()
    backtests.component.html # ADD: W/L cards (abort guard + per-strategy card with table)
tests/
  test_report.py     # ADD: W/L analysis tests
```

### Pattern 1: Signal Dataclass Extension (4 new optional fields)

**What:** Add four `Optional[float]` fields with `None` defaults to the Signal dataclass in `simulate.py`.

**When to use:** Established pattern from Phase 1-2 (industry_group, industry_momentum, industry_above_50ma, industry_rank_pct). None defaults ensure backward compatibility with all positional-arg callsites.

```python
# Source: simulator.py — extension following Phase 2 precedent
@dataclass
class Signal:
    # ... existing fields unchanged ...
    # Phase 2 — industry momentum
    industry_group: Optional[str] = None
    industry_momentum: Optional[float] = None
    industry_above_50ma: Optional[bool] = None
    industry_rank_pct: Optional[float] = None
    # Phase 4 — W/L analysis entry-time metrics (all Optional; None = not available)
    rsi_entry: Optional[float] = None
    rvol: Optional[float] = None
    pullback_depth_pct: Optional[float] = None   # None for breakout signals
    pct_to_52w_high: Optional[float] = None
```

**Key constraint:** These fields are NOT stored as dedicated DB columns — the signals table has no `rsi_entry` column. They exist only in memory during a backtest run and are consumed by `render_report()`. The computed analysis is stored in `backtest_reports.metrics_json`.

### Pattern 2: Metric Extraction in backtest.py generate_signals()

**What:** After calling `fn(ticker, daily_sliced, ctx, precomp=precomp_t)`, extract the four new metrics from the strategy result and pass them into Signal construction.

**RVOL for pullback:** PullbackResult has no `vol_ratio` field. Compute from precomp: `float(daily_sliced['Volume'].iloc[-1]) / float(precomp_t.vol_sma50.asof(as_of_ts))`. Guard against NaN / zero denominator.

**pct_to_52w_high for pullback:** PullbackResult has no `pct_to_52w_high`. Compute as `result.close / float(precomp_t.high_52w.asof(as_of_ts)) * 100`. Guard against NaN / zero.

```python
# Source: backtest.py — after fn() call, before Signal() construction
# Metric extraction (strategy-polymorphic)
_rsi = getattr(result, 'rsi', None)
_rvol = getattr(result, 'vol_ratio', None)  # BreakoutResult only
if _rvol is None and precomp_t is not None:
    # Pullback: compute RVOL from precomp (vol_sma50 series)
    _vol_sma50 = float(precomp_t.vol_sma50.asof(as_of_ts))
    _cur_vol = float(daily_sliced['Volume'].iloc[-1])
    if _vol_sma50 > 0 and not pd.isna(_vol_sma50) and not pd.isna(_cur_vol):
        _rvol = _cur_vol / _vol_sma50
_pullback_depth = getattr(result, 'pullback_depth_pct', None)  # PullbackResult only
_pct_high = getattr(result, 'pct_to_52w_high', None)  # BreakoutResult only
if _pct_high is None and precomp_t is not None:
    # Pullback: compute pct_to_52w_high from precomp (high_52w series)
    _h52 = precomp_t.high_52w.asof(as_of_ts)
    if not pd.isna(_h52) and float(_h52) > 0:
        _pct_high = result.close / float(_h52) * 100
```

**Important:** Use `getattr(result, 'field', None)` for strategy-polymorphic access. Both `PullbackResult` and `BreakoutResult` have `.rsi`; only BreakoutResult has `.vol_ratio` and `.pct_to_52w_high`; only PullbackResult has `.pullback_depth_pct`. This pattern avoids `isinstance()` checks.

### Pattern 3: WL_FEATURES Pre-Registration (WLA-06 guard)

**What:** A module-level constant in report.py listing the exact features to analyze. This constant is the sole source of truth — the analysis function iterates it in order, no dynamic selection.

```python
# Source: report.py — module level, committed before results are viewed (WLA-06)
WL_FEATURES = [
    'RSI at entry',
    'RVOL',
    'Pullback depth %',
    'ATR multiple',
    'Industry momentum',
    'Pct to 52w high',
]
WL_MIN_TOTAL  = 200  # total qualified trades below this → abort analysis
WL_MIN_BUCKET = 50   # winner_n OR loser_n below this → suppress strategy
```

**Why it matters:** The ADX and volume-contraction gate reversal failures were caused by examining results and then choosing which gates to report. WLA-06 prevents the same pattern from infecting the W/L analysis. The list must be in source control before the first full backtest run.

### Pattern 4: wl_characteristic_analysis() Function

**What:** Standalone function in report.py (same pattern as `gate_attribution()`, `failure_analysis()`, `stop_out_forensics()`). Takes signals and qualified trades, returns a dict matching the JSON shape from UI-SPEC.

**Metric source per feature:**

| WL_FEATURES entry | Source | Notes |
|---|---|---|
| `'RSI at entry'` | `Signal.rsi_entry` | Via `sig_by_key` lookup |
| `'RVOL'` | `Signal.rvol` | Via `sig_by_key` lookup |
| `'Pullback depth %'` | `Signal.pullback_depth_pct` | None for breakout → excluded from medians |
| `'ATR multiple'` | `Trade.target_atr` | Already on Trade, no Signal lookup needed |
| `'Industry momentum'` | `Signal.industry_momentum` | Already on Signal |
| `'Pct to 52w high'` | `Signal.pct_to_52w_high` | Via `sig_by_key` lookup |

**Signal lookup key:** `(str(t.signal_date), t.ticker, t.strategy)` — include strategy to avoid collisions if a future "both" backtest run produces same (date, ticker) for two strategies.

**Median computation:** Use sorted-list midpoint (no new imports): `sorted_vals[n//2]` for odd length, `(sorted_vals[n//2-1] + sorted_vals[n//2]) / 2` for even.

**Winner classification:** `t.r_multiple > 0` (consistent with `compute_metrics()`). Losers: `t.r_multiple <= 0`. Only from `_active_trades()` (qualified=True, r_multiple not None).

```python
# Source: report.py — wl_characteristic_analysis()
def wl_characteristic_analysis(
    signals: list[Signal],
    qualified_trades: list[Trade],
) -> dict:
    """Pre-registered W/L characteristic analysis. (WLA-01 through WLA-06)"""
    active = _active_trades(qualified_trades)
    total = len(active)

    if total < WL_MIN_TOTAL:
        return {
            'total_qualified': total,
            'aborted': True,
            'abort_reason': (
                f'Insufficient data — fewer than {WL_MIN_TOTAL} qualified trades '
                f'(n={total}). W/L analysis suppressed.'
            ),
            'strategies': [],
        }

    sig_by_key = {(str(s.date), s.ticker, s.strategy): s for s in signals}
    strategies_present = sorted(set(t.strategy for t in active))
    strategy_results = []

    for strat in strategies_present:
        strat_active = [t for t in active if t.strategy == strat]
        winners = [t for t in strat_active if t.r_multiple > 0]
        losers  = [t for t in strat_active if t.r_multiple <= 0]
        w_n, l_n = len(winners), len(losers)

        if w_n < WL_MIN_BUCKET or l_n < WL_MIN_BUCKET:
            strategy_results.append({
                'strategy': strat,
                'winner_n': w_n,
                'loser_n': l_n,
                'suppressed': True,
                'suppression_reason': (
                    f'Suppressed — fewer than {WL_MIN_BUCKET} trades in winner or '
                    f'loser bucket (winners: {w_n}, losers: {l_n}).'
                ),
                'rows': [],
            })
            continue

        rows = []
        for metric in WL_FEATURES:
            w_vals = _extract_wl_metric(metric, winners, sig_by_key)
            l_vals = _extract_wl_metric(metric, losers,  sig_by_key)
            w_med = _safe_median(w_vals)
            l_med = _safe_median(l_vals)
            delta = (round(w_med - l_med, 4) if w_med is not None and l_med is not None else None)
            rows.append({
                'metric': metric,
                'winners_median': round(w_med, 4) if w_med is not None else None,
                'losers_median':  round(l_med, 4) if l_med is not None else None,
                'delta': delta,
            })

        strategy_results.append({
            'strategy': strat,
            'winner_n': w_n,
            'loser_n': l_n,
            'suppressed': False,
            'suppression_reason': None,
            'rows': rows,
        })

    return {
        'total_qualified': total,
        'aborted': False,
        'abort_reason': None,
        'strategies': strategy_results,
    }
```

### Pattern 5: render_report() Extension

**What:** Call `wl_characteristic_analysis()` near the start of `render_report()`, emit markdown section after the "Target Distance Analysis — by ATR multiple" section, and include in `json_out`.

**Placement in markdown:** After `ta_buckets` rendering, before gate attribution. This matches 04-UI-SPEC.md placement (after target ATR, before trade list).

**json_out addition:**
```python
wl_result = wl_characteristic_analysis(signals, qualified_trades)
json_out['wl_analysis'] = wl_result
```

**Markdown pattern for abort state:**
```
## Winner/Loser Characteristic Analysis (Pre-registered)

> **Warning:** Insufficient data — fewer than 200 qualified trades (n=87). Analysis suppressed.
```

**Markdown pattern for suppressed strategy:**
```
### Pullback

> **Warning:** Suppressed — fewer than 50 trades in winner or loser bucket (winners: 12, losers: 89).
```

**Markdown pattern for normal (6-row table):**
```
### Pullback (winners: 142, losers: 200)

| Metric                   | Winners | Losers  | Delta   |
|--------------------------|---------|---------|---------|
| RSI at entry             | 52.3    | 48.7    | +3.6    |
| RVOL                     | 1.45x   | 1.22x   | +0.23   |
| Pullback depth %         | -8.2%   | -10.1%  | +1.9%   |
| ATR multiple             | 1.20    | 1.45    | -0.25   |
| Industry momentum (20d)  | +3.4%   | -0.8%   | +4.2%   |
| Pct to 52w high          | 18.3%   | 22.7%   | -4.4%   |
```

### Pattern 6: API Extension (runs.js)

**What:** One line added inside the `if (reportData.metrics)` block. Follows the established pattern for all other fields.

```javascript
// Source: web/api/routes/runs.js — inside if (reportData.metrics) block
result.wl_analysis = reportData.wl_analysis || null;
```

### Pattern 7: Angular Component Addition

**What:** Follow the existing backtests.component.ts pattern: getter + format helpers + template fragment + import addition.

All interfaces go in `api.service.ts` after `GateAttrib`. `wl_analysis` is added as an optional field to `Run`. The component class follows the getter + helper pattern. No new CSS classes.

```typescript
// Source: api.service.ts — interfaces (from 04-UI-SPEC.md)
export interface WlMetricRow {
  metric: string;
  winners_median: number | null;
  losers_median: number | null;
  delta: number | null;
}
export interface WlStrategyAnalysis {
  strategy: string;
  winner_n: number;
  loser_n: number;
  suppressed: boolean;
  suppression_reason: string | null;
  rows: WlMetricRow[];
}
export interface WlAnalysis {
  total_qualified: number;
  aborted: boolean;
  abort_reason: string | null;
  strategies: WlStrategyAnalysis[];
}
// Add to Run interface: wl_analysis?: WlAnalysis | null;
```

```typescript
// Source: backtests.component.ts — additions
get wlAnalysis(): WlAnalysis | null {
  return this.selectedRun?.wl_analysis ?? null;
}
fmtWlValue(metric: string, value: number | null): string {
  if (value == null) return '—';
  switch (metric) {
    case 'RSI at entry':      return value.toFixed(1);
    case 'RVOL':              return value.toFixed(2) + 'x';
    case 'Pullback depth %':  return (value >= 0 ? '+' : '') + value.toFixed(1) + '%';
    case 'ATR multiple':      return value.toFixed(2);
    case 'Industry momentum': return (value >= 0 ? '+' : '') + value.toFixed(1) + '%';
    case 'Pct to 52w high':   return value.toFixed(1) + '%';
    default:                  return value.toFixed(2);
  }
}
fmtWlDelta(metric: string, delta: number | null): string {
  if (delta == null) return '—';
  const sign = delta >= 0 ? '+' : '';
  switch (metric) {
    case 'RSI at entry':      return sign + delta.toFixed(1);
    case 'RVOL':              return sign + delta.toFixed(2);
    case 'Pullback depth %':  return sign + delta.toFixed(1) + '%';
    case 'ATR multiple':      return sign + delta.toFixed(2);
    case 'Industry momentum': return sign + delta.toFixed(1) + '%';
    case 'Pct to 52w high':   return sign + delta.toFixed(1) + '%';
    default:                  return sign + delta.toFixed(2);
  }
}
```

```html
<!-- Source: backtests.component.html — W/L cards (per 04-UI-SPEC.md) -->
<div class="warning-box" *ngIf="wlAnalysis?.aborted">
  {{ wlAnalysis!.abort_reason }}
</div>
<ng-container *ngIf="wlAnalysis && !wlAnalysis.aborted">
  <div class="card" *ngFor="let s of wlAnalysis.strategies">
    <h2>W/L Analysis — {{ s.strategy | titlecase }}</h2>
    <p class="section-desc">
      Pre-registered entry-time metrics (6). Feature list defined in
      <code>report.py</code> source code before results were viewed.
    </p>
    <div class="warning-box" *ngIf="s.suppressed">
      {{ s.suppression_reason }}
    </div>
    <table *ngIf="!s.suppressed">
      <thead>
        <tr>
          <th>Metric</th>
          <th class="num">Winners (n={{ s.winner_n }})</th>
          <th class="num">Losers (n={{ s.loser_n }})</th>
          <th class="num">Delta</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let row of s.rows">
          <td>{{ row.metric }}</td>
          <td class="num">{{ fmtWlValue(row.metric, row.winners_median) }}</td>
          <td class="num">{{ fmtWlValue(row.metric, row.losers_median) }}</td>
          <td class="num">{{ fmtWlDelta(row.metric, row.delta) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</ng-container>
```

### Anti-Patterns to Avoid

- **Storing new metric fields as dedicated DB columns:** No schema bump needed. The W/L analysis lives in `backtest_reports.metrics_json`. Avoid adding `rsi_entry`, `rvol`, etc. to the signals table.
- **Dynamic feature selection at runtime:** WLA-06 requires the feature list to be fixed in source code. Do NOT select features based on data availability or significance tests.
- **Using `isinstance(result, PullbackResult)` to branch:** Use `getattr(result, 'field', None)` for strategy-polymorphic metric extraction. Cleaner and avoids import cycles.
- **Color-coding the Delta column in the UI:** 04-UI-SPEC.md explicitly prohibits this. Metric directionality is ambiguous (higher RSI in winners is good; higher pullback depth may be ambiguous). Use default body color for delta.
- **Including near-miss trades in W/L analysis:** Only `_active_trades(qualified_trades)` contribute. Near-miss trades are never included (consistent with all other report sections).
- **Matching Trade→Signal by (date, ticker) only:** Use `(date, ticker, strategy)` to avoid any future collision.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Median computation | Custom percentile/average logic | Sorted-list midpoint (stdlib) or `pd.Series.median()` | 2-line implementation is correct; no edge cases missed |
| Winner classification | Custom R threshold logic | `t.r_multiple > 0` — consistent with `compute_metrics()` | Consistency is critical; one definition of "winner" everywhere |
| JSON shape for wl_analysis | Ad-hoc dict structures | The exact shape from 04-UI-SPEC.md | Angular component is pre-specced to exact field names |
| Per-strategy grouping | Custom loop structure | `set(t.strategy for t in active)` + sorted | One-liner; clean |

**Key insight:** Phase 4 is pure data plumbing and display. All hard algorithmic work (signal generation, simulation, DB storage) is done in prior phases. Phase 4 aggregates existing data into a new report section.

---

## Common Pitfalls

### Pitfall 1: Metric Values for Wrong Strategy
**What goes wrong:** `pullback_depth_pct` is None for breakout signals. If the analysis function doesn't handle None gracefully, all breakout rows for "Pullback depth %" will throw.
**Why it happens:** The 6 metrics are defined for all strategies, but some are only meaningful for one (depth for pullback, vol_ratio in breakout's native form vs computed for pullback).
**How to avoid:** `_extract_wl_metric()` must build a list of non-None floats. If all values are None for a metric in a given strategy, `_safe_median()` returns None → cell shows `—`. This is correct behavior.
**Warning signs:** Median table shows `—` for all breakout rows in "Pullback depth %" — that is expected and correct.

### Pitfall 2: Signal Lookup Miss
**What goes wrong:** W/L analysis cannot match a Trade to its Signal if the Signal was not in the signals list passed to render_report().
**Why it happens:** In scan.py cmd_backtest(), all signals (qualified + near-miss) are passed to render_report(). Near-miss signals that became trades (simulate_trades runs on q_signals only) will not cause lookup misses because we only look up qualified trades. But if `signals` list is filtered before passing to render_report(), lookups will fail.
**How to avoid:** The existing `render_report()` call in scan.py passes ALL signals: `render_report(signals, q_trades, nm_trades, run_meta)`. No change needed.

### Pitfall 3: precomp_t None Guard
**What goes wrong:** `precomp_t.vol_sma50.asof(as_of_ts)` raises AttributeError if precomp_t is None.
**Why it happens:** `precomp_by_ticker.get(ticker)` may return None for tickers that failed pre-computation. The existing code already guards with `precomp_t = precomp_by_ticker.get(ticker)`.
**How to avoid:** Wrap all precomp access in `if precomp_t is not None:` and fall back to `None` for the metric. The Signal field stays None, the trade is excluded from that metric's median (since `_safe_median([])` returns None).

### Pitfall 4: pct_to_52w_high Formula Direction
**What goes wrong:** BreakoutResult stores `pct_to_52w_high = close / high_52w * 100` (e.g., 97.5 meaning 97.5% of high, i.e., 2.5% below). If pullback uses `(high_52w - close) / high_52w * 100` (which gives 2.5), the two strategies use different sign conventions.
**How to avoid:** Use `close / high_52w * 100` for both strategies (same formula as BreakoutResult). The W/L feature is labeled "Pct to 52w high" — the example in UI-SPEC shows values like 18.3% and 22.7%, which are consistent with `(1 - pct_to_52w_high/100) * 100` distance from high. But looking at the BreakoutResult: `pct_to_52w_high = round(pct_to_high * 100, 2)` where `pct_to_high = close / high_52w_val`. So 97.5 means close is 97.5% of 52w high.

Wait — the UI-SPEC example shows 18.3% for winners and 22.7% for losers as "Pct to 52w high". These values represent distance-from-high, NOT pct-of-high. 18.3% below high is realistic for a pullback winner. So the formula is likely `(high_52w - close) / high_52w * 100`.

**Resolution:** Use `(high_52w - close) / high_52w * 100` for pullback signals, and compute consistently for breakout: `(100 - BreakoutResult.pct_to_52w_high)` to convert "97.5% of high" to "2.5% below high". This represents "how far below 52w high is the stock at signal time" — a positive value where smaller = closer to high.

Alternatively, define `pct_to_52w_high` on Signal as "% of 52w high" (BreakoutResult's native format), and document that smaller = farther from high in the UI. For the display, just show the raw value. The UI-SPEC example values (18.3, 22.7) suggest it's "% below high" — use `(high_52w - close) / high_52w * 100`.

**Final decision (ASSUMED — confirm with owner):** Store as `(high_52w - close) / high_52w * 100` = "percent distance below 52w high". Smaller values mean closer to the high (less pullback from high). For breakout: `100 - result.pct_to_52w_high` to get the same convention.

### Pitfall 5: DB Ingest of New Signal Fields
**What goes wrong:** `store_db.insert_signals_batch()` ignores unknown fields from `sig.get("rsi_entry")` — but `asdict(s)` in scan.py produces a dict with the 4 new keys. The INSERT statement doesn't include these columns, so they'll be silently ignored by SQLite. This is correct.
**Why it happens:** The INSERT uses named columns: `(date, ticker, ..., industry_rank_pct)`. Extra keys in the dict are ignored.
**How to avoid:** No action needed — this is correct behavior. Verify that insert_signal() and insert_signals_batch() do not use `**sig` in a way that passes unknown kwargs to SQLite.
**Verification:** Both insert functions use explicit column lists in SQL, so extra keys in the dict are harmless.

### Pitfall 6: RVOL NaN from precomp
**What goes wrong:** `precomp_t.vol_sma50.asof(as_of_ts)` returns NaN when insufficient volume history exists for the rolling mean.
**How to avoid:** Always guard: `if not pd.isna(_vol_sma50) and _vol_sma50 > 0`.

---

## Code Examples

### _safe_median helper
```python
# Source: local implementation — no new imports needed
def _safe_median(values: list) -> Optional[float]:
    """Median of a list of floats; None if empty."""
    if not values:
        return None
    s = sorted(v for v in values if v is not None)
    if not s:
        return None
    n = len(s)
    mid = n // 2
    return float(s[mid]) if n % 2 == 1 else float((s[mid - 1] + s[mid]) / 2)
```

### _extract_wl_metric helper
```python
# Source: local implementation — Pattern 4 above
def _extract_wl_metric(
    metric: str,
    trades: list[Trade],
    sig_by_key: dict,
) -> list[float]:
    """Return non-None metric values for a list of trades."""
    values = []
    for t in trades:
        key = (str(t.signal_date), t.ticker, t.strategy)
        sig = sig_by_key.get(key)
        if metric == 'RSI at entry':
            v = sig.rsi_entry if sig else None
        elif metric == 'RVOL':
            v = sig.rvol if sig else None
        elif metric == 'Pullback depth %':
            v = sig.pullback_depth_pct if sig else None
        elif metric == 'ATR multiple':
            v = t.target_atr
        elif metric == 'Industry momentum':
            v = sig.industry_momentum if sig else None
        elif metric == 'Pct to 52w high':
            v = sig.pct_to_52w_high if sig else None
        else:
            v = None
        if v is not None:
            values.append(float(v))
    return values
```

### Markdown formatter for a metric row
```python
# Source: local implementation — CLI format table rows
def _fmt_wl_value(metric: str, v: Optional[float]) -> str:
    if v is None:
        return '—'  # em dash
    if metric == 'RSI at entry':      return f'{v:.1f}'
    if metric == 'RVOL':              return f'{v:.2f}x'
    if metric == 'Pullback depth %':  return f'{v:+.1f}%'
    if metric == 'ATR multiple':      return f'{v:.2f}'
    if metric == 'Industry momentum': return f'{v:+.1f}%'
    if metric == 'Pct to 52w high':   return f'{v:.1f}%'
    return f'{v:.2f}'
```

---

## Runtime State Inventory

> Not applicable — Phase 4 is a pure extension of the report pipeline. No rename, rebrand, or migration involved. No existing DB state is modified; `backtest_reports.metrics_json` gains a new key (`wl_analysis`) in new runs only. Existing rows are unaffected.

**Nothing found in category:** None — verified by codebase analysis.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib | `_safe_median()` — sorted list | ✓ | 3.x | — |
| pandas | `precomp_t.vol_sma50.asof()`, NaN guards | ✓ | already installed | — |
| Angular | backtests component template | ✓ | already installed | — |
| Node.js / Express | runs.js API extension | ✓ | already running | — |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (Python), Karma/Jasmine (Angular) |
| Config file | `pytest.ini` or auto-discovered |
| Quick run command | `pytest tests/test_report.py -q` |
| Full suite command | `pytest -q && cd web/api && npm test && cd ../ui && ng test --watch=false` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WLA-01 | wl_analysis present in json_out when >= 200 trades | unit | `pytest tests/test_report.py::test_render_report_has_wl_analysis -x` | ❌ Wave 0 |
| WLA-01 | median values correct for hand-fixture | unit | `pytest tests/test_report.py::test_wl_analysis_basic -x` | ❌ Wave 0 |
| WLA-02 | exactly 6 metric rows | unit | `pytest tests/test_report.py::test_wl_analysis_six_metrics -x` | ❌ Wave 0 |
| WLA-03 | per-strategy split | unit | `pytest tests/test_report.py::test_wl_analysis_per_strategy -x` | ❌ Wave 0 |
| WLA-04 | industry_momentum in rows | unit | `pytest tests/test_report.py::test_wl_analysis_has_industry_momentum -x` | ❌ Wave 0 |
| WLA-05 | bucket < 50 → suppressed | unit | `pytest tests/test_report.py::test_wl_analysis_suppressed -x` | ❌ Wave 0 |
| WLA-06 | WL_FEATURES is a fixed list constant | unit | `pytest tests/test_report.py::test_wl_features_is_constant -x` | ❌ Wave 0 |
| WLA-04 | total < 200 → aborted | unit | `pytest tests/test_report.py::test_wl_analysis_abort -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_report.py -q`
- **Per wave merge:** `pytest -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] New test functions in `tests/test_report.py` — covers WLA-01 through WLA-06
- [ ] Angular spec update in `web/ui/src/app/pages/backtests/backtests.component.spec.ts` — add wlAnalysis getter + fmtWlValue/fmtWlDelta tests

*(Wave 0 gaps are new test additions, not a new test file — test_report.py already exists)*

---

## Security Domain

> `security_enforcement` is enabled (absent key = enabled in config.json).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not applicable — no auth in Phase 4 |
| V3 Session Management | no | Not applicable |
| V4 Access Control | no | Not applicable — API is read-only |
| V5 Input Validation | yes (LOW risk) | The `wl_analysis` JSON is produced server-side from the metrics_json blob, not from user input |
| V6 Cryptography | no | Not applicable |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Injection via run_id in GET /api/runs/:run_id | Tampering | run_id is used in parameterized SQLite query — already protected |
| JSON.parse on untrusted metrics_json | Tampering | metrics_json is only written by the backtest command (internal); the API reads but does not modify it |

**Assessment:** Phase 4 is a display-only extension. The wl_analysis dict is computed server-side from Signal + Trade objects produced by the scanner engine, not from user-supplied data. No new attack surface is introduced.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual post-hoc analysis of backtest results | Pre-registered feature list committed before runs | This phase | Prevents multiple-comparisons bias (ADX/volume-contraction failure mode) |
| Sector-level ETF proxy only | Industry-level ETF proxy map (Phase 1-2) | Phase 1-2 | Industry momentum now available as discriminating dimension |

**Deprecated/outdated:**
- Ad-hoc selection of which metrics to compare: replaced by `WL_FEATURES` constant. The WLA-06 requirement exists specifically because previous gate decisions (ADX, volume contraction) were influenced by viewing results without pre-registration.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | pct_to_52w_high should be stored as `(high_52w - close) / high_52w * 100` (% below high), consistent with the UI-SPEC example values (18.3%, 22.7%) | Pitfall 4 | If "% of high" (97.5%) is intended instead, the breakout formula and display format label both change. UI-SPEC examples are ambiguous. Confirm with owner before backtest ingestion. |
| A2 | "ATR multiple" in WL_FEATURES refers to `Trade.target_atr` (target distance in ATRs), not `(entry - stop) / atr` | Pattern 4 | If it means stop-risk in ATRs (which is always 1.0 by stop definition), the metric would have no discriminating value. `target_atr` (example values 1.20 vs 1.45) makes more analytical sense. |

**If this table is empty:** It isn't — these two items need clarification before the first production backtest run.

---

## Open Questions

1. **pct_to_52w_high formula direction (A1 above)**
   - What we know: BreakoutResult stores `close / high_52w * 100` (e.g., 97.5%). UI-SPEC example shows 18.3% / 22.7% for pullback winners/losers.
   - What's unclear: The UI-SPEC example values match `(high_52w - close) / high_52w * 100` (distance format) but BreakoutResult uses the ratio format.
   - Recommendation: Use `(high_52w - close) / high_52w * 100` for both strategies. Confirm with owner. The display label "Pct to 52w high" implies distance, not ratio.

2. **"ATR multiple" definition (A2 above)**
   - What we know: `Trade.target_atr = (target - entry_px) / signal.atr` is already computed and stored.
   - What's unclear: Whether the user means target distance or stop distance in ATRs.
   - Recommendation: Use `Trade.target_atr`. It has discriminating value (winner targets may be more realistic). Stop distance in ATRs is constant by the stop rule definition.

---

## Sources

### Primary (HIGH confidence)
- `scanner/simulate.py` — Signal and Trade dataclasses, all field definitions
- `scanner/report.py` — existing report structure, all functions, render_report() signature
- `scanner/backtest.py` — generate_signals() loop, Signal construction, PrecomputedBars
- `scanner/strategies/pullback.py` — PullbackResult fields (rsi, pullback_depth_pct, vol_contraction)
- `scanner/strategies/breakout.py` — BreakoutResult fields (rsi, vol_ratio, pct_to_52w_high)
- `scanner/store_db.py` — DB schema v9, insert_signal(), signals table columns
- `web/api/routes/runs.js` — API endpoint structure, metrics_json parsing pattern
- `web/ui/src/app/services/api.service.ts` — existing TypeScript interfaces and Run type
- `web/ui/src/app/pages/backtests/backtests.component.ts` — component pattern (getters, format helpers)
- `.planning/phases/04-winner-loser-characteristic-analysis/04-UI-SPEC.md` — locked UI contract (JSON shape, Angular template, CSS constraints, copy)
- `.planning/REQUIREMENTS.md` — WLA-01 through WLA-06 definitions
- `tests/test_report.py` — existing test patterns for report functions

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — confirmed Phase 4 pre-registration decision locked in Decisions section
- `.planning/ROADMAP.md` — success criteria details for Phase 4

---

## Metadata

**Confidence breakdown:**
- Signal dataclass extension: HIGH — direct code inspection, exact same pattern as Phase 2
- Metric extraction from strategy results: HIGH — all source fields confirmed in PullbackResult/BreakoutResult
- RVOL computation for pullback: HIGH — precomp.vol_sma50 confirmed in PrecomputedBars; formula is standard
- pct_to_52w_high formula direction: LOW — formula direction ambiguous from UI-SPEC example; owner confirmation required
- ATR multiple definition: MEDIUM — target_atr on Trade confirmed; interpretation of the label is assumed
- render_report() extension pattern: HIGH — clear from existing code; same pattern used 4 times already
- Angular additions: HIGH — per 04-UI-SPEC.md (already approved)
- API extension: HIGH — one-liner, exact pattern confirmed in runs.js

**Research date:** 2026-07-01
**Valid until:** 2026-08-01 (stable codebase; all dependencies pre-installed)
