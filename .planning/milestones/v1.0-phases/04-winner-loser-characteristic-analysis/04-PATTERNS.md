# Phase 4: Winner/Loser Characteristic Analysis - Pattern Map

**Mapped:** 2026-07-01
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scanner/simulate.py` | model | request-response | `scanner/simulate.py` lines 15-33 (Phase 2 extension) | exact |
| `scanner/backtest.py` | service | batch | `scanner/backtest.py` lines 426-450 (Phase 2 industry block) | exact |
| `scanner/report.py` | service | transform | `scanner/report.py` — `gate_attribution()`, `stop_out_forensics()`, `render_report()` | exact |
| `scanner/store_db.py` | utility | CRUD | no change needed — verified harmless | N/A |
| `web/api/routes/runs.js` | route | request-response | `web/api/routes/runs.js` lines 45-55 (if-block pattern) | exact |
| `web/ui/src/app/services/api.service.ts` | service | request-response | `api.service.ts` lines 89-141 (interface + Run type) | exact |
| `web/ui/src/app/pages/backtests/backtests.component.ts` | component | request-response | `backtests.component.ts` lines 40-88 (getter + format helper pattern) | exact |
| `web/ui/src/app/pages/backtests/backtests.component.html` | component | request-response | existing `.card` + `.warning-box` + `<table>` blocks | exact |
| `tests/test_report.py` | test | batch | `tests/test_report.py` lines 34-80 (_trade/_signal helpers) | exact |

---

## Pattern Assignments

### `scanner/simulate.py` — Signal dataclass extension (4 new optional fields)

**Analog:** `scanner/simulate.py` lines 29-33 (Phase 2 addition)

**Existing optional field pattern** (lines 29-33):
```python
# Phase 2 — industry momentum (all Optional; None-defaulted so positional callers unaffected)
industry_group: Optional[str] = None
industry_momentum: Optional[float] = None
industry_above_50ma: Optional[bool] = None
industry_rank_pct: Optional[float] = None
```

**New fields to append immediately after line 33:**
```python
# Phase 4 — W/L analysis entry-time metrics (all Optional; None = not available)
rsi_entry: Optional[float] = None
rvol: Optional[float] = None
pullback_depth_pct: Optional[float] = None   # None for breakout signals
pct_to_52w_high: Optional[float] = None
```

**Key constraint:** These fields are NOT stored as DB columns. The signals table INSERT uses explicit column lists and extra dataclass fields are ignored by SQLite. No schema bump needed.

---

### `scanner/backtest.py` — populate 4 new Signal fields in generate_signals()

**Analog:** `scanner/backtest.py` lines 426-450 (industry momentum block, the last block before `signals.append()`)

**Existing industry block pattern** (lines 426-450):
```python
# Industry momentum — reuse per-day cached strength (sliced_market only)
_strength = day_ind_cache.get(ticker) or {"industry_etf": None, "industry_mom_20d": None, "industry_above_50ma": None}
_etf = _strength.get("industry_etf")
_rank_pct: Optional[float] = None
if _etf is not None and _etf in day_rank.index:
    _rv = day_rank[_etf]
    _rank_pct = float(_rv) if not _pd.isna(_rv) else None
_q_sig = quality_by_ticker.get(ticker)
signals.append(Signal(
    date=d,
    ticker=ticker,
    strategy=strategy,
    score=result.score,
    confidence=result.confidence,
    stop=result.suggested_stop,
    target=result.suggested_target,
    atr=result.atr or 0.0,
    qualified=result.qualified,
    failed_gates=list(result.failed_gates),
    close=result.close,
    industry_group=getattr(_q_sig, "industry", None),
    industry_momentum=_strength.get("industry_mom_20d"),
    industry_above_50ma=_strength.get("industry_above_50ma"),
    industry_rank_pct=_rank_pct,
))
```

**Insert before `signals.append()` — metric extraction block (new for Phase 4):**
```python
# Phase 4 — W/L entry-time metric extraction (strategy-polymorphic via getattr)
_rsi = getattr(result, 'rsi', None)
_rvol = getattr(result, 'vol_ratio', None)   # BreakoutResult only
if _rvol is None and precomp_t is not None:
    # Pullback: compute RVOL from precomp vol_sma50 series
    _vol_sma50 = float(precomp_t.vol_sma50.asof(as_of_ts))
    _cur_vol = float(daily_sliced['Volume'].iloc[-1])
    if _vol_sma50 > 0 and not pd.isna(_vol_sma50) and not pd.isna(_cur_vol):
        _rvol = _cur_vol / _vol_sma50
_pullback_depth = getattr(result, 'pullback_depth_pct', None)   # PullbackResult only
_pct_high = getattr(result, 'pct_to_52w_high', None)            # BreakoutResult only
if _pct_high is None and precomp_t is not None:
    # Pullback: pct below 52w high = (high_52w - close) / high_52w * 100
    _h52 = precomp_t.high_52w.asof(as_of_ts)
    if not pd.isna(_h52) and float(_h52) > 0:
        _pct_high = (float(_h52) - result.close) / float(_h52) * 100
```

**Extend `Signal(...)` call with 4 new kwargs** (after `industry_rank_pct=_rank_pct,`):
```python
    rsi_entry=_rsi,
    rvol=_rvol,
    pullback_depth_pct=_pullback_depth,
    pct_to_52w_high=_pct_high,
```

**Breakout pct_to_52w_high convention note:** BreakoutResult stores `pct_to_52w_high = close / high_52w * 100` (e.g., 97.5). Convert to distance format: `100 - result.pct_to_52w_high` so both strategies produce "% below 52w high" (positive = farther below). Apply this conversion when `_pct_high` comes from the getattr (BreakoutResult). Guard: only convert if result is BreakoutResult — use `getattr(result, 'vol_ratio', None) is not None` as a proxy since only BreakoutResult has `vol_ratio`.

---

### `scanner/report.py` — WL_FEATURES constant + 3 new functions + render_report() extension

**Analog:** `scanner/report.py` lines 15-18 (module-level constants pattern) and `gate_attribution()` lines 159-212, `stop_out_forensics()` lines 305-376, `render_report()` lines 392-629.

**Module-level constants pattern** (lines 15-18):
```python
SCORE_BUCKETS = [(40, 54), (55, 69), (70, 84), (85, 999)]
CONF_LEVELS = ["LOW", "MEDIUM", "HIGH"]
MIN_BUCKET_N = 20
MIN_ATTRIBUTION_N = 30
```

**New constants to add at module level (same section):**
```python
# Phase 4 — W/L characteristic analysis (pre-registered; WLA-06 guard)
WL_FEATURES = [
    'RSI at entry',
    'RVOL',
    'Pullback depth %',
    'ATR multiple',
    'Industry momentum',
    'Pct to 52w high',
]
WL_MIN_TOTAL  = 200   # total qualified trades below this → abort analysis
WL_MIN_BUCKET = 50    # winner_n OR loser_n below this → suppress strategy
```

**`_active_trades()` analog for understanding winner classification** (lines 37-39):
```python
def _active_trades(trades: list[Trade]) -> list[Trade]:
    """Qualified trades with a valid R (excludes gap-skips and incomplete)."""
    return [t for t in trades if t.qualified and t.r_multiple is not None]
```

**`gate_attribution()` docstring + return structure pattern** (lines 159-162):
```python
def gate_attribution(
    all_trades: list[Trade],
    qualified_expectancy: float,
) -> list[dict]:
    """Per-gate attribution: near-misses failing ONLY that gate vs qualified."""
```

**`stop_out_forensics()` early-return guard pattern** (lines 318-324):
```python
if n_stop_outs == 0:
    return {
        "n_stop_outs": 0,
        "pct_reached_target": None,
        ...
        "interpretation": "No stop-out trades to analyze.",
    }
```

**`render_report()` json_out assembly pattern** (lines 614-627):
```python
json_out = {
    "metrics": metrics,
    "score_buckets": score_buckets,
    ...
    "target_atr_buckets": ta_buckets,
    "biases": [_BIAS_SURVIVORSHIP, _BIAS_LOOK_AHEAD],
    "run_meta": run_meta or {},
    "trades": trades_list,
}
```

**Placement of W/L section in `render_report()` markdown:** After the `ta_buckets` rendering block (after line ~548) and before the gate attribution block (before line ~550). Add W/L to `json_out` just before the `return` at line 629.

**`render_report()` markdown warning pattern** (lines 414-421):
```python
amb_warning = (
    f"\n> **Warning:** {amb_pct:.1%} of trade bars are ambiguous ..."
    if amb_pct > 0.15 else ""
)
```

**New functions to add (full implementations from RESEARCH.md):**

`_safe_median(values)` — sorted-list midpoint, no new imports, returns `Optional[float]`.

`_extract_wl_metric(metric, trades, sig_by_key)` — builds non-None float list per WL_FEATURES entry; `ATR multiple` reads from `t.target_atr` directly (no Signal lookup needed).

`wl_characteristic_analysis(signals, qualified_trades)` — groups by strategy, applies WL_MIN_TOTAL and WL_MIN_BUCKET gates, computes medians via `_safe_median`, returns the JSON dict shape specified in 04-UI-SPEC.md.

`_fmt_wl_value(metric, v)` — mirrors the Angular `fmtWlValue` switch, used for the markdown table column cells.

---

### `web/api/routes/runs.js` — add wl_analysis to the if-block

**Analog:** `web/api/routes/runs.js` lines 45-55 (the entire `if (reportData.metrics)` block)

**Existing pattern to extend** (lines 45-55):
```javascript
if (reportData.metrics) {
  result.metrics            = reportData.metrics;
  result.score_buckets      = reportData.score_buckets      || [];
  result.conf_buckets       = reportData.conf_buckets       || [];
  result.gate_attribution   = reportData.gate_attribution   || [];
  result.monthly_signals    = reportData.monthly_signals    || {};
  result.trades             = reportData.trades             || [];
  result.failure_analysis   = reportData.failure_analysis    || null;
  result.stop_out_forensics = reportData.stop_out_forensics  || null;
  result.target_r_buckets   = reportData.target_r_buckets    || [];
  result.target_atr_buckets = reportData.target_atr_buckets  || [];
}
```

**One line to append inside the block (after `target_atr_buckets`):**
```javascript
  result.wl_analysis = reportData.wl_analysis || null;
```

---

### `web/ui/src/app/services/api.service.ts` — 3 new interfaces + Run extension

**Analog:** `api.service.ts` lines 89-141 (StopOutForensics, FailureAnalysis, TargetBucket, GateAttrib interfaces + Run interface)

**Existing interface pattern** (lines 89-121):
```typescript
export interface StopOutForensics {
  n_stop_outs: number;
  pct_reached_target: number | null;
  ...
}
export interface GateAttrib {
  gate: string;
  n: number;
  expectancy_r: number | null;
  ...
}
```

**New interfaces to add after `GateAttrib` (line 121):**
```typescript
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
```

**Run interface extension** (after `target_atr_buckets` on line 141):
```typescript
wl_analysis?: WlAnalysis | null;
```

---

### `web/ui/src/app/pages/backtests/backtests.component.ts` — getter + format helpers

**Analog:** `backtests.component.ts` lines 40-88 (getter pattern) and lines 117-137 (format helper pattern)

**Existing getter pattern** (lines 60-64):
```typescript
get failureAnalysis(): FailureAnalysis | null {
  return this.selectedRun?.failure_analysis ?? null;
}
```

**Existing format helper pattern** (lines 117-130):
```typescript
fmt(v: number | null | undefined): string {
  if (v == null) return '—';
  return (v * 100).toFixed(1) + '%';
}

fmtR(v: number | null | undefined): string {
  if (v == null) return '—';
  return (v >= 0 ? '+' : '') + v.toFixed(2) + 'R';
}
```

**New getter to add (after `hasTargetAtrData` getter, line 87):**
```typescript
get wlAnalysis(): WlAnalysis | null {
  return this.selectedRun?.wl_analysis ?? null;
}
```

**New format helpers to add (after `wlAnalysis` getter):**
```typescript
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

**Import line extension** (line 1):
```typescript
import { ..., WlAnalysis } from '../../services/api.service';
```

---

### `web/ui/src/app/pages/backtests/backtests.component.html` — W/L cards

**Analog:** Existing `.card` blocks, `.warning-box` blocks, and `<table>` blocks in `backtests.component.html`.

**Placement:** Insert after the "Target Distance — by ATR" card block, before the "Trade list" card.

**Full template to insert (from 04-UI-SPEC.md — locked):**
```html
<!-- W/L analysis — abort warning -->
<div class="warning-box" *ngIf="wlAnalysis?.aborted">
  {{ wlAnalysis!.abort_reason }}
</div>

<!-- W/L analysis — per-strategy cards -->
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

**No new CSS classes.** All classes used (`.card`, `.warning-box`, `.num`, `<h2>`, `.section-desc`, `table`/`th`/`td`) already exist in `backtests.component.css` and `styles.css`.

---

### `tests/test_report.py` — W/L analysis tests (new test functions in existing file)

**Analog:** `tests/test_report.py` lines 34-80 (`_trade()` and `_signal()` helper pattern)

**Existing `_trade()` helper** (lines 34-73):
```python
def _trade(
    r: float,
    exit_reason: str = "target",
    score: float = 60.0,
    confidence: str = "MEDIUM",
    qualified: bool = True,
    failed_gates: list | None = None,
    signal_date: date = date(2026, 1, 2),
    exit_date: date = date(2026, 1, 12),
    flags: dict | None = None,
    target_r: float | None = None,
    target_atr: float | None = None,
    ...
) -> Trade:
    return Trade(
        ticker="TEST",
        signal_date=signal_date,
        ...
    )
```

**Existing `_signal()` helper** (lines 76-80):
```python
def _signal(qualified=True, failed_gates=None, sig_date=date(2026, 3, 5)) -> Signal:
    return Signal(
        date=sig_date,
        ticker="TEST",
        strategy="pullback",
```

**New imports to add to the import block** (after line 28):
```python
from scanner.report import (
    ...
    wl_characteristic_analysis,
    WL_FEATURES,
    WL_MIN_TOTAL,
    WL_MIN_BUCKET,
)
```

**New helper function** (extend `_trade()` to accept `target_atr` — already present — and add `_wl_signal()`):
```python
def _wl_signal(
    ticker="TEST",
    strategy="pullback",
    r_entry=50.0,
    rvol=1.5,
    depth=8.0,
    industry_momentum=3.0,
    pct_high=15.0,
    sig_date=date(2026, 1, 2),
) -> Signal:
    return Signal(
        date=sig_date,
        ticker=ticker,
        strategy=strategy,
        score=60.0,
        confidence="MEDIUM",
        stop=90.0,
        target=120.0,
        atr=2.0,
        qualified=True,
        rsi_entry=r_entry,
        rvol=rvol,
        pullback_depth_pct=depth,
        industry_momentum=industry_momentum,
        pct_to_52w_high=pct_high,
    )
```

**New test functions to add (cover WLA-01 through WLA-06 + abort):**

- `test_wl_features_is_constant` — assert `WL_FEATURES` is a list with exactly 6 items (WLA-06)
- `test_wl_analysis_abort` — build fewer than 200 qualified trades, assert `result['aborted'] is True`
- `test_wl_analysis_basic` — hand-fixture with 100+ winners + 100+ losers, assert medians correct
- `test_wl_analysis_six_metrics` — assert `len(result['strategies'][0]['rows']) == 6` (WLA-02)
- `test_wl_analysis_per_strategy` — mix pullback+breakout signals/trades, assert two strategy entries (WLA-03)
- `test_wl_analysis_suppressed` — bucket with fewer than 50 winners, assert `suppressed is True` (WLA-05)
- `test_wl_analysis_has_industry_momentum` — assert `'Industry momentum'` metric present in rows (WLA-04)
- `test_render_report_has_wl_analysis` — call `render_report()` with 200+ trades, assert `'wl_analysis' in json_out` (WLA-01)

---

## Shared Patterns

### `_active_trades()` filter
**Source:** `scanner/report.py` lines 37-39
**Apply to:** `wl_characteristic_analysis()` — use the existing helper directly; do not reimplement.
```python
active = _active_trades(qualified_trades)
```

### Optional[float] field declaration
**Source:** `scanner/simulate.py` lines 29-33
**Apply to:** All 4 new Signal fields — same `Optional[float] = None` pattern, same trailing-field placement.

### getattr() strategy-polymorphic access
**Source:** RESEARCH.md Pattern 2
**Apply to:** `backtest.py` metric extraction block — use `getattr(result, 'field', None)` for all 4 metrics to avoid isinstance() checks and import cycles.

### Sorted-list midpoint median
**Source:** RESEARCH.md Code Examples + `report.py` lines 75-78 (existing median pattern for `holding_days`)
```python
holding = sorted(t.holding_days for t in active if t.holding_days is not None)
median_hold = holding[len(holding) // 2] if holding else None
```
**Apply to:** `_safe_median()` implementation in `report.py`.

### json_out key addition
**Source:** `scanner/report.py` lines 614-627
**Apply to:** Add `'wl_analysis': wl_result` to `json_out` dict before the `return` statement (line ~629).

### Signal lookup key
**Source:** `scanner/report.py` lines 589-590 (existing `sig_by_key` using `(date_str, ticker)`)
```python
sig_by_key = {(str(s.date), s.ticker): s for s in signals}
```
**Phase 4 variation:** Use `(str(s.date), s.ticker, s.strategy)` as the key to handle future "both" strategy runs. Different key from the existing one in `render_report()` — define separately in `wl_characteristic_analysis()`.

---

## No Analog Found

None. All 9 files have exact or role-match analogs in the codebase.

---

## Metadata

**Analog search scope:** `scanner/`, `web/api/routes/`, `web/ui/src/app/`, `tests/`
**Files scanned:** 8 source files read directly
**Pattern extraction date:** 2026-07-01
