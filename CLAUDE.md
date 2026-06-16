# Swing Scanner — Merge, Backtest & Refactor Backlog (v2, grounded in actual sources)

**Implementer prerequisites:** You have the three source files. READ THEM FIRST, in this order:
1. `pullback_filter.py` (799 lines) — the architectural reference. Modern gate-accumulator pattern.
2. `breakout_filter.py` (209 lines) — legacy short-circuit pattern; will be rewritten onto the pullback architecture.
3. `swing_scanner.py` (1790 lines) — legacy monolith; will be mined for assets (target engine, regime, ATH, confidence, EVAL_DATE concept) and then retired.

All line numbers below refer to these exact files. If a line number is off by a few lines after earlier tasks have modified the file, locate the construct by the quoted function/variable name.

**End-state architecture (what we're building toward):**

```
scanner/                      # package
  __init__.py
  data_store.py               # E1 — Parquet-cached OHLCV, the ONLY module that imports yfinance for prices
  earnings_store.py           # E5.3 — cached earnings dates
  core.py                     # E2 — GateLog, EvalContext, QualityInfo, shared indicators
  targets.py                  # E4.1 — stop/target engine ported from swing_scanner
  regime.py                   # E4.2 — market regime + ATH analysis
  strategies/
    pullback.py               # E2.3 — evaluate() ported from pullback_filter._evaluate
    breakout.py               # E3.1 — rewritten onto GateLog architecture
  backtest.py                 # E6
  simulate.py                 # E7 — trade simulator (shared by backtest + journal resolve)
  report.py                   # E8
  store_db.py                 # E9 — owns ALL SQL; data/scanner.db (SQLite, Postgres-swappable)
  journal.py                  # E9 — live signal writer / resolver / compare (calls store_db)
  universe.py                 # E10
scan.py                       # single CLI: scan | diagnose | backtest | journal | universe | worker
tests/
legacy/swing_scanner.py       # parked after E4

web/                          # E12 — separate app, never imports Python
  api/                        # Express (Node, plain JS), better-sqlite3, READ-ONLY on scanner.db
  ui/                         # Angular SPA (localhost:4200)
```

Data flow: Python engine (manual or scheduled) → writes `data/scanner.db` → Express API reads it → Angular renders. On-demand actions go the other way through a `jobs` table the Python `worker` polls (E12.6). The parquet OHLCV cache stays internal to the engine; the website does not read it.

**Global conventions (every task):**
- Python 3.11+, type hints on public functions, dataclasses for records.
- After E1 lands: no `yf.` imports outside `data_store.py` / `earnings_store.py`. No `datetime.now()` / `pd.Timestamp.now()` inside evaluation logic.
- Do NOT change gate thresholds, gate sets, or score formulas unless the task explicitly says so. Where the three files disagree (they do — see Appendix A), the pullback_filter / breakout_filter values WIN and the swing_scanner values are discarded, except where a task states otherwise.
- Every Python task ends with `pytest -q` green, offline. Web tasks (E12) instead end green on their own toolchain (`npm test` for the API, `ng test` for the UI) and must not break `pytest`.
- Any deviation from spec (because the code surprised you) must be documented in the task summary.

**Critical-path order:** E0 → E1 → E2 → (E3 ∥ E4) → E5 → E6 → E7 → E8. E9 (persistence) anytime after E6.1 has the Signal shape; E10 anytime after E2. E11 after the engine is complete. E12 (website) depends on E9 being in place — build it after the engine produces a populated `scanner.db`.

---

## EPIC E0 — Scaffolding & Golden-Master Regression Harness

Goal: lock in current behavior BEFORE refactoring, so every later epic can prove it changed nothing it wasn't supposed to.

### E0.1 — Repo scaffolding
**Description:** Create the package skeleton above (empty modules with docstrings), `pyproject.toml` or `requirements.txt` (`yfinance`, `pandas`, `numpy`, `ta`, `pyarrow`, `pandas_market_calendars`, `pytest`, `pytest-cov`), `tests/` with `conftest.py`, and a `Makefile` or `tasks.md` with `make test`. Copy the three source files into the repo root unchanged (they keep working as-is until their retirement tasks).

**Acceptance criteria:**
1. `python -c "import scanner"` works; `pytest -q` runs (0 tests is fine).
2. `python pullback_filter.py --help` and `python swing_scanner.py --help` still work unchanged from repo root.

**Estimate:** S.

### E0.2 — Synthetic fixture factories
**Description:** In `tests/conftest.py`, build deterministic (seeded) OHLCV DataFrame factories matching what yfinance returns (`Open/High/Low/Close/Volume` float columns, `DatetimeIndex`, ≥260 rows so 252-day rolling windows in both filters are satisfied — note `pullback_filter.scan_pullbacks` line 670 and `breakout_filter._history` line 78 both require ≥220 rows):
- `make_pullback_setup()` — uptrend (SMA50>SMA200 rising), recent 40d swing high, 3–20 day pullback of 4–18% depth holding above the prior swing low, contracting volume, RSI in 40–60 — i.e., engineered to pass every price-based gate in `pullback_filter._evaluate`.
- `make_breakout_setup()` — close ≥97% of 252d high, close above prior 20d consolidation high, last-bar volume ≥1.5× SMA50 volume, close>SMA50>SMA200, RSI in 55–75, ADX≥20, BB width in lowest 40% of trailing 60d, ≥$5M ADV — engineered to pass every price-based gate in `breakout_filter._evaluate`.
- `make_downtrend()`, `make_choppy()` — engineered to fail.
- `make_quality(**overrides)` — returns the dict shape of `pullback_filter._quality` (line 195): `profitable, market_cap (e.g. 2.5e9), debt_equity, sector ("Technology"), float_shares`.
- `make_market_data()` — dict of `{"SPY": df, "XLK": df, ...}` synthetic frames for all symbols in `SECTOR_ETF_MAP` (pullback_filter line 99), shaped like `prefetch_market_data()` output.

Getting the pass-everything fixtures right is fiddly (ADX and BB-percentile especially). Iterate: run the actual evaluators against the fixture, read the verbose gate log, adjust until green. Budget real time for this.

**Acceptance criteria:**
1. `pullback_filter._evaluate("SYN", make_pullback_setup(), make_quality(), make_market_data(), verbose=True)` returns `qualified=True` — with `_earnings_proximity` and `_weekly_trend` monkeypatched (they hit the network; patch to return `30` and `{"weekly_above_30ma": True, "weekly_30ma_rising": True}`).
2. `breakout_filter._evaluate("SYN", make_breakout_setup(), make_quality())` returns a `BreakoutResult` (not None).
3. Downtrend/choppy fixtures fail the respective evaluators.
4. All factories deterministic: two calls produce identical frames.

**Estimate:** M/L. **Dependencies:** E0.1.

### E0.3 — Golden-master snapshots
**Description:** Pytest tests that run the CURRENT evaluators on the E0.2 fixtures and assert against frozen expected values (checked-in JSON): for pullback — `qualified`, `failed_gates`, `gates_passed`, `gates_total`, `score` (±0.1), and 6 representative numeric fields (`pullback_depth_pct`, `rsi`, `adx`, `vol_contraction`, `rs_strength`, `ma200_distance_pct`); for breakout — all `BreakoutResult` fields (±0.1 on floats). Add one near-miss variant per strategy (perturb the fixture to fail exactly one named gate) and snapshot that too.

These snapshots are the refactor contract: E2/E3 tasks must keep them green (modulo explicitly-allowed diffs each task lists).

**Acceptance criteria:**
1. Snapshots committed; tests green offline.
2. A deliberate threshold change (e.g., edit `RSI_PULLBACK_RANGE`) makes the snapshot test fail — proving sensitivity. Revert.

**Estimate:** M. **Dependencies:** E0.2.

---

## EPIC E1 — Data Layer (`scanner/data_store.py`)

Replaces: `pullback_filter._fetch_history` (line 169) + `prefetch_market_data` (line 180) + module global `_market_data_cache` (line 166); `breakout_filter._history` (line 74); `swing_scanner.fetch_data` (line 290) incl. its `EVAL_DATE`/`DROP_INCOMPLETE` logic, `fetch_ath` + `_ath_cache` (line 322–324).

### E1.1 — Parquet cache for daily OHLCV
**Description:** As specified:
- `get_history(ticker, end: date | None = None, refresh: bool = False) -> pd.DataFrame | None` — full cached history, sliced to `index.date <= end` when given (the slicing pattern already exists at swing_scanner line 311: `df[df.index.date <= EVAL_DATE]` — reuse it). Returns None if (after slicing) fewer than 220 rows, mirroring current minimums.
- `refresh_ticker(ticker)` — incremental tail fetch with adjusted-data invalidation: after fetching, compare `Close` on the overlap date; >0.1% mismatch ⇒ drop cache, full re-fetch (`period="max", auto_adjust=True`).
- `refresh_universe(tickers, pause=0.2) -> RefreshReport` (`succeeded / failed[(ticker, err)] / invalidated`). The 0.2s politeness sleep currently in `scan_pullbacks` (line 676) and `scan_breakouts` (line 168 of breakout_filter) moves HERE — scanning cached data needs no sleeps.

Storage `data/ohlcv/{TICKER}.parquet`. Strip yfinance's tz-aware index to tz-naive dates at write time; document in module docstring. Wrap every yfinance call in `fetch_with_retry` (3 attempts, exponential backoff + jitter, `logging` logger `scanner.data`, WARNING per retry).

**Acceptance criteria:**
1. Two `get_history` calls ⇒ one network fetch (mock-counted).
2. Split-invalidation unit test (synthetic pre/post 2:1 frames) triggers full re-fetch.
3. `get_history(t, end=d)` max index date ≤ d (test on synthetic cache files written directly to tmp dir — no network in tests).
4. Corrupt parquet ⇒ treated as missing, no crash.
5. Retry wrapper: fail-twice-then-succeed mock ⇒ result + 2 warnings; always-fail ⇒ raises after 3.

**Estimate:** M/L.

### E1.2 — Derived series: weekly bars and ATH
**Description:**
- `get_weekly(ticker, end=None) -> pd.DataFrame | None` — resample cached daily to `W-FRI` (first Open, max High, min Low, last Close, sum Volume), DROP the trailing partial week, slice to `end`. This replaces BOTH `pullback_filter._weekly_trend`'s separate `interval="1wk"` fetch (line 345) and `swing_scanner.check_weekly_trend` (line 678). Note the two legacy functions disagree (30w MA vs 10w MA, and opposite missing-data defaults — see Appendix A); the MA computation itself stays in the strategy/context layer, not here.
- `get_ath(ticker, end=None) -> float | None` — max High of cached full history up to `end`. Replaces `fetch_ath`/`_ath_cache`; the zone labeling (NEW_ATH/NEAR_ATH/…, swing_scanner lines 324–388) moves to `regime.py` in E4.2.

**Acceptance criteria:**
1. Weekly resample of a hand-built 15-day daily frame matches hand-computed OHLCV; partial final week excluded (test with `end` falling midweek).
2. `get_ath` with `end` before a later spike returns the pre-spike high (point-in-time correctness).

**Estimate:** M. **Dependencies:** E1.1.

### E1.3 — Market-data bundle
**Description:** `get_market_data(end=None) -> dict[str, pd.DataFrame]` returning `{"SPY": ..., "XLK": ..., ...}` for SPY + the 11 ETFs in `SECTOR_ETF_MAP` (move the map into `scanner/core.py`), all from cache, all sliced to `end`. Replaces `prefetch_market_data` and the `_market_regime_cache` SPY fetch in `swing_scanner.check_market_regime` (line 628).

**Acceptance criteria:**
1. Zero yfinance calls when cache is warm (mock raises).
2. All 12 frames share the same max date when `end` given.

**Estimate:** S. **Dependencies:** E1.1.

---

## EPIC E2 — Core Extraction & Point-in-Time Purity (`scanner/core.py`, `scanner/strategies/pullback.py`)

### E2.1 — `GateLog` class
**Description:** Lift the closure trio from `pullback_filter._evaluate` (lines 368–391: `gate`, `bonus`, `section`, plus `failed_gates` list and `gate_count`) into a reusable class:

```python
class GateLog:
    def __init__(self, ticker: str, verbose: bool = False): ...
    def section(self, title: str) -> None
    def gate(self, name: str, passed: bool, detail: str = "") -> bool
    def skip(self, name: str, reason: str) -> None        # NEW — see E2.2
    def bonus(self, name: str, present: bool, detail: str = "") -> None
    # properties: failed_gates: list[str], skipped_gates: list[str],
    #             gates_passed: int, gates_total: int  (total EXCLUDES skipped),
    #             qualified: bool  (no failed gates)
```

Preserve the exact verbose output format (`✓/✗ name (detail)` under section headers) — the diagnose UX must not change. Skipped gates print as `– name (skipped: reason)`.

**Acceptance criteria:**
1. Unit tests for counts, `qualified`, and skip exclusion from `gates_total`.
2. Verbose output for a pass/fail/skip sequence matches a frozen expected string.

**Estimate:** S/M. **Dependencies:** E0.1.

### E2.2 — `EvalContext` + pure `evaluate()` for pullback
**Description:** The heart of the refactor. In `core.py`:

```python
@dataclass(frozen=True)
class QualityInfo:        # field-for-field from pullback_filter._quality (line 195)
    profitable: bool
    market_cap: float | None
    debt_equity: float | None
    sector: str | None
    float_shares: float | None

@dataclass(frozen=True)
class EvalContext:
    as_of: date
    market_data: dict[str, pd.DataFrame]   # from E1.3, sliced
    weekly: pd.DataFrame | None            # from E1.2, sliced
    quality: QualityInfo
    days_to_earnings: int | None           # None = UNKNOWN (replaces the 999 sentinel)
```

Port `_evaluate` (lines 358–649) to `scanner/strategies/pullback.py` as `evaluate(ticker, df, ctx, verbose=False) -> PullbackResult`, with these and ONLY these behavioral changes (each must keep/adjust golden masters explicitly):

a) **Earnings gate** (lines 525–528): currently `_earnings_proximity` returns 999 when unknown ⇒ gate silently PASSES. New: `ctx.days_to_earnings is None` ⇒ `log.skip("Earnings clear", "no earnings data")`; known value ⇒ gate as before (`> EARNINGS_BUFFER_DAYS`). Network call moves to the context factory (E2.4).

b) **Sector gate** (lines 538–544): currently unknown sector ⇒ `gate(..., True, "sector unknown — skipped")` — recorded as PASSED, inflating `gates_passed`. New: `log.skip("Sector strength", "sector unknown")`. Known sector but missing ETF frame ⇒ also skip.

c) **Weekly gate** (lines 546–548): currently `_weekly_trend(ticker)` fetches inside the evaluator and a fetch failure defaults to `{False, False}` ⇒ gate FAILS on a data problem. New: compute `weekly_above_30ma` / `weekly_30ma_rising` from `ctx.weekly` (30-period MA on closed weekly bars, rising = MA[-1] > MA[-5], exactly mirroring lines 348–350); `ctx.weekly is None` or <35 rows ⇒ skip, not fail.

d) **Market cap / D/E gates** (lines 554–564): currently `mc is None` ⇒ FAILS, `de is None` ⇒ PASSES — inconsistent. New: both skip when None. (Profitability stays a hard gate even when info was unfetchable — `profitable=False` is the conservative default and that's intentional; document it.)

e) **No wall clock:** any date logic uses `ctx.as_of`.

Everything else — all thresholds, the support-candidate logic (lines 473–507), score formula (lines 583–600), result fields — ports verbatim. Two additive `PullbackResult` changes: new fields `as_of: date` and `skipped_gates: str`; and change `failed_gates`/`skipped_gates` to `list[str]` internally with semicolon-joining done only at CSV-export time (the dataclass keeps lists; `_print_results`/CSV writer joins). Keep `pullback_filter.py` as a thin shim that imports from the package (full retirement in E4.4).

**Acceptance criteria:**
1. Zero network and zero wall-clock in `evaluate` (yfinance monkeypatched to raise; `datetime.now` patched to raise).
2. Golden masters (E0.3) green EXCEPT the enumerated diffs: with fully-populated context, results identical; with earnings/sector/weekly/mc/de unknowns, the named gates appear in `skipped_gates` and `gates_total` drops accordingly — update snapshots for the unknown-variants only, with a written justification per diff.
3. New unit tests: one per semantic change (a)–(d) above.

**Estimate:** L — the largest task in the backlog. **Dependencies:** E2.1, E1.2, E1.3, E0.3.

### E2.3 — Helper migration
**Description:** Move to `core.py` unchanged: `_bullish_reversal_candle` (line 221), `_pocket_pivot` (247), `_nr7` (263), `_rs_metrics` (271), `_sector_strength` (316, signature now takes `market_data` from ctx), `SECTOR_ETF_MAP` (99), and all threshold constants (lines 56–92). `_sector_strength` and `_rs_metrics` are shared with breakout in E3.

**Acceptance criteria:**
1. Existing E0.2-fixture behavior unchanged (golden masters green).
2. No duplicate definitions remain in `pullback_filter.py` (it imports from `scanner.core`).

**Estimate:** S. **Dependencies:** E2.2 (do together).

### E2.4 — Context factory
**Description:** `core.make_context(ticker, as_of: date | None = None) -> EvalContext | None`:
- `as_of=None` (live): `as_of` = last date of the ticker's cached daily frame; market data + weekly from E1; quality via the live `_quality` (move to `core.py`, keep best-effort try/except shape, route through retry wrapper); `days_to_earnings` via the existing `.calendar` parser (port `_earnings_proximity` lines 291–313, but: return `None` instead of 999 on unknown, and compute days relative to `as_of` not `Timestamp.now()` — for live use these coincide).
- historical `as_of`: everything sliced to `as_of`; `days_to_earnings=None` until E5.3; quality = current values (documented look-ahead, see E6.4).

Also `make_contexts(tickers, as_of=None)` batch variant that loads market data once.

**Acceptance criteria:**
1. Historical context: every frame's max date ≤ `as_of` (daily, weekly, all 12 market frames) — tested against synthetic cache.
2. Live path on a warm cache performs only quality+calendar network calls.
3. Earnings parser unit-tested against the three `.calendar` shapes the current code handles (dict, DataFrame-with-index, list) plus None ⇒ returns None.

**Estimate:** M. **Dependencies:** E2.2, E1.x.

---

## EPIC E3 — Breakout Parity Rewrite (`scanner/strategies/breakout.py`)

### E3.1 — Rewrite breakout onto GateLog/EvalContext — SAME gate set
**Description:** Reimplement `breakout_filter._evaluate` (lines 96–166) as `evaluate(ticker, df, ctx, verbose=False) -> BreakoutResult` with full (non-short-circuit) evaluation. Gate-for-gate mapping, names fixed as: `"Near 52w high"` (≥`NEAR_HIGH_PCT`, line 101), `"Consolidation breakout"` (close ≥ prior-20d high excluding today, line 107 — note it uses `.iloc[-CONSOL_LOOKBACK-1:-1]`, keep that exclusion exactly), `"Volume confirmation"` (vol_ratio ≥1.5 vs SMA50 volume, line 112), `"Trend alignment"` (close>SMA50>SMA200, line 118), `"RSI in breakout range"` (55–75), `"ADX trend strength"` (≥20), `"BB squeeze"` (width ≤ 40th pctile of trailing 60d, line 135), `"Liquidity"` ($5M ADV-50, line 141), `"Market cap in range"`, `"Profitable"`, `"Debt/equity acceptable"`.

Apply E2.2's skip semantics to the quality gates (mc/de None ⇒ skip; profitable stays hard). Extend `BreakoutResult` with `qualified, failed_gates: list[str], skipped_gates: list[str], gates_passed, gates_total, as_of`. Score formula (lines 148–153) verbatim. NO new gates in THIS task — the approved earnings gate is added separately in E3.3 so its golden-master diff is isolated and attributable.

**Acceptance criteria:**
1. E0.3 breakout golden master green for the qualifying fixture (same numbers, plus new fields).
2. The near-miss fixture now RETURNS a result (legacy returned None) with exactly one entry in `failed_gates` — update snapshot with justification.
3. Verbose diagnose output format matches pullback's section style.

**Estimate:** M. **Dependencies:** E2.1–E2.4, E0.3.

### E3.2 — Shared scan loop
**Description:** `core.run_scan(tickers, strategy_fn, as_of=None, verbose=False, capture_all=True) -> pd.DataFrame` — replaces `scan_pullbacks` (line 656) and `scan_breakouts` (line 159 of breakout_filter): refresh cache (live mode only) → `make_contexts` → evaluate each → DataFrame sorted `qualified` desc then `score` desc. Keep the `[i/n]` progress line behavior (pullback_filter line 667).

**Acceptance criteria:**
1. Both strategies scan the E0.2 fixtures through one code path (inject frames via a test seam — e.g., the loop takes an optional `history_provider` callable defaulting to `data_store.get_history`).
2. No sleeps in the loop (they live in `refresh_universe`).

**Estimate:** S/M. **Dependencies:** E3.1.

### E3.3 — Add earnings-proximity gate to breakout [APPROVED 2026-06-11 — changes trading logic]
**Description:** Decision resolved by István: the earnings gate is a risk-policy filter (protects against scheduled binary gaps through the stop), not an edge filter, so it applies to both strategies. Rationale on record: breakouts cluster around catalysts and the volume gate is biased toward selecting pre-earnings anticipation; the tight breakout stop (`high_20_prev − 0.5·ATR`) on $300M–5B names cannot contain an earnings gap; and the E7 simulator structurally underestimates gap losses (fills stop-outs at the stop price), so E8 attribution could never validate this gate honestly.

Implementation:
- Add gate `"Earnings clear"` to `scanner/strategies/breakout.py::evaluate`, identical semantics to pullback (E2.2a): `ctx.days_to_earnings > EARNINGS_BUFFER_DAYS` to pass; `None` ⇒ `log.skip("Earnings clear", "no earnings data")`. `EARNINGS_BUFFER_DAYS` (=7) is the single shared constant in `scanner/core.py` — both strategies import it; do not duplicate.
- Place the gate in the same "Filters" section position as pullback's, so diagnose output reads consistently across strategies.
- Add `days_to_earnings: int | None` field to `BreakoutResult` (mirrors `PullbackResult`).
- CLI escape hatch: `scan.py scan --allow-earnings` disables this gate for BOTH strategies in live scans (forces skip with reason "disabled by --allow-earnings"). Default off. This exists for deliberate pre-earnings trades, which are a different setup with different management — the flag makes that an explicit choice rather than a silent gap. The backtest equivalent is the existing `--earnings-gate {on,off}` (E5.3); do not add a second backtest flag.
- Note the asymmetry this preserves: a breakout the day AFTER a report (gap-and-go) still passes — the gate only excludes holding INTO an announcement within the buffer.

**Acceptance criteria:**
1. Unit tests: `days_to_earnings=3` ⇒ gate fails, listed in `failed_gates`; `=10` ⇒ passes; `=None` ⇒ in `skipped_gates`, excluded from `gates_total`.
2. E0.3 breakout golden masters updated: the qualifying fixture (monkeypatched `days_to_earnings=30`) keeps `qualified=True` with `gates_total` incremented by exactly 1; snapshot diff justified in the task summary as "E3.3 approved gate addition".
3. `--allow-earnings` forces skip on both strategies (one test each); flag absent ⇒ gate active.
4. `grep -rn "EARNINGS_BUFFER_DAYS" scanner/` shows exactly one definition (core.py) and imports elsewhere.

**Estimate:** S/M. **Dependencies:** E3.1, E2.4 (context carries `days_to_earnings`).

### E3.4 — DEFERRED DECISION: RS / sector / weekly gates for breakout
**Description:** The remaining three pullback-side gates (RS vs SPY, sector strength, weekly trend) are selection-quality filters, not risk filters — E8.3 attribution CAN evaluate them honestly. NO implementation now. After the first full backtest run (E6/E8 complete), produce a one-page note with the attribution numbers for these criteria on the pullback side plus a recommendation per gate for breakout. István decides; approved gates become follow-up tasks tagged "changes trading logic" with golden-master updates.

**Acceptance criteria:** 1. Note exists with per-gate numbers and recommendation. 2. No code changes in this task.
**Estimate:** S. **Dependencies:** E8.3.

---

## EPIC E4 — Mine swing_scanner Assets, Then Retire It

### E4.1 — Port the target/stop engine (`scanner/targets.py`) — REQUIRED BY THE SIMULATOR
**Description:** Neither filter computes stops or targets today; the trade simulator (E7) cannot run without them. Port from swing_scanner:
- `compute_targets(df, price, stop, setup, atr) -> TargetAnalysis` (line 459) with `TargetMethod`/`TargetAnalysis` dataclasses (lines 243–257) — the 5-method confluence engine. Port verbatim; pure function, no I/O.
- `count_resistance_obstacles(df, price, target)` (line 710) — verbatim.
- Stop rules, exactly as legacy: pullback `stop = round(ema20 − atr, 2)` (line 1055); breakout `stop = round(high_20_prev − 0.5·atr, 2)` (line 1217). EMA20/ATR(14) computed in `core.py` indicators.
- New `attach_risk(result, df) -> result` step in `run_scan` that populates new result fields `suggested_stop`, `suggested_target`, `risk_reward`, `atr` on qualified rows of BOTH strategies (near-misses: populate too — the simulator needs them for E8.3 attribution).

**Acceptance criteria:**
1. Unit test on a synthetic frame: each of the 5 target methods produces hand-verified values; confluence zone and conservative `suggested_target` match hand computation.
2. Stop formulas match the legacy lines bit-for-bit on the same input frame (port test: run legacy function vs new on one fixture).
3. Both strategies' scan output now contains stop/target/RR columns.

**Estimate:** M/L. **Dependencies:** E3.2.

### E4.2 — Port market regime + ATH zones (`scanner/regime.py`)
**Description:**
- `market_regime(market_data) -> Literal["BULLISH","BEARISH","NEUTRAL","UNKNOWN"]` — logic from `check_market_regime` (lines 628–677: SPY close vs SMA50 and EMA20), but consuming the E1.3 bundle instead of fetching; drop the module cache (the bundle is already cached).
- `ath_zone(ticker, close, end=None) -> tuple[float, float, str]` — port zone labels/thresholds from `fetch_ath` (lines 324–388) on top of `data_store.get_ath`.
- Regime is DISPLAY + confidence input only (as today, swing_scanner lines 1693–1698 just print warnings) — it must NOT become a gate.
- Wire into scan output: a regime banner line, and per-row `ath_zone` column.

**Acceptance criteria:**
1. Regime unit tests: synthetic SPY above both MAs ⇒ BULLISH; below both ⇒ BEARISH; mixed ⇒ NEUTRAL; <50 rows ⇒ UNKNOWN.
2. `ath_zone` point-in-time test: `end` before a later spike labels relative to the pre-spike ATH.

**Estimate:** M. **Dependencies:** E1.2, E1.3.

### E4.3 — Port confidence rating
**Description:** `compute_confidence` (lines 742–815) moves to `regime.py` verbatim (point values untouched), with inputs adapted: `weekly_aligned` ⇐ pullback's `weekly_above_30ma` or breakout ctx weekly; `rr` ⇐ E4.1; `sma_slope`/`macd_bullish` — compute in `core.py` indicators the same way swing_scanner's `compute_indicators` (line 389) does (read it; port just those two series). Add `confidence` column to scan output; add `--high-only` filter to the CLI (E4.5).

**Acceptance criteria:**
1. Unit test: hand-built input combos hit HIGH (≥12), MEDIUM (7–11), LOW (<7) boundaries exactly, including the ATH-zone ±points.

**Estimate:** S/M. **Dependencies:** E4.1, E4.2.

### E4.4 — Risk-based position sizing
**Description:** Replace the hard-coded sizing at swing_scanner lines 1375–1381 (`shares = int(650 / r.price)`) with `core.position_size(entry, stop, account_size, risk_pct, max_position) -> SizeInfo`: `shares = floor((account_size·risk_pct)/(entry−stop))`, capped by `max_position/entry`; warn when cap binds; `entry ≤ stop` ⇒ 0 shares with message, no ZeroDivisionError. CLI defaults: `--account-size 6500 --risk-pct 0.01 --max-position 650`. Shown in diagnose output and as columns in scan output.

**Acceptance criteria:**
1. Unit test: account 6500, risk 1%, entry 10.00, stop 9.50 ⇒ 130 shares ⇒ capped to 65 by max-position 650, cap warning present.
2. Stop ≥ entry ⇒ size 0, message, exit code 0.

**Estimate:** S. **Dependencies:** E4.1.

### E4.5 — Unified CLI (`scan.py`) and legacy retirement
**Description:** Single entry point with subcommands:
- `scan.py scan --strategy {pullback,breakout,both} [--file U.txt | --tickers A,B | --ticker X] [--csv out.csv] [--show-all] [--verbose] [--high-only] [--min-score N] [--date YYYY-MM-DD] [--no-journal]` — `--date` reuses `make_context(as_of=...)` (this replaces swing_scanner's EVAL_DATE mode, lines 41–42 and 1647–1657); `--ticker` implies verbose diagnose (preserving `diagnose_ticker` UX, pullback_filter line 689).
- `scan.py refresh --file U.txt` — cache warm-up (E1).
- stubs registered for `backtest` / `journal` / `universe` (filled by E6/E9/E10).
- Market-hours behavior: port the closed/live candle logic (swing_scanner lines 1661–1675) but on top of `pandas_market_calendars` XNYS (holidays + half-days), as `core.last_closed_session(now)`; in cache terms "drop incomplete bar" = refresh then drop the last row if its date == today and session still open.
- Then retire: move `swing_scanner.py` to `legacy/` with a deprecation banner naming the replacement commands; delete `TIER0–TIER3` lists, `backtest_setups` (superseded by E6 — its inline simplified pullback conditions at lines 838–860 duplicate and CONTRADICT pullback_filter, see Appendix A), and the shims `pullback_filter.py`/`breakout_filter.py` become 5-line deprecation wrappers calling `scan.py`.

**Acceptance criteria:**
1. `scan.py scan --strategy pullback --ticker AAPL` (warm synthetic cache + mocked quality) reproduces the diagnose gate log.
2. Calendar tests: 2026-01-01 (holiday), day-after-Thanksgiving 13:00 ET close, normal Wednesday 20:00 ET, Saturday.
3. `grep -rn "TIER1_MIDCAPS\|backtest_setups" --include=*.py .` ⇒ only `legacy/`.
4. README updated with the new commands.

**Estimate:** M/L. **Dependencies:** E4.1–E4.4, E3.2.

---

## EPIC E5 — Historical Inputs Completion

### E5.1 — (merged into E2.4 — no separate task)
### E5.2 — Universe history bootstrap
**Description:** `scan.py refresh` gains `--full` to force `period="max"` re-fetch; add a bootstrap doc snippet (expected cache size, ~25–35 min for 2,000 tickers with the 0.2s pause — the rate currently in `scan_pullbacks`).
**Acceptance criteria:** 1. `--full` invalidates and refetches (mock-verified). **Estimate:** XS. **Dependencies:** E1.1.

### E5.3 — Historical earnings store (`scanner/earnings_store.py`)
**Description:** `get_earnings_dates(ticker) -> list[date]` via `yf.Ticker(t).get_earnings_dates(limit=60)`, Parquet-cached, retry-wrapped. `days_to_earnings(ticker, as_of) -> int | None`: distance to the first known date strictly after `as_of`; None if no data or the latest known date predates `as_of` by >90 days (too sparse to trust). Wire into `make_context` for historical `as_of`; backtest flag `--earnings-gate {on,off}` (default on; off forces skip).

**Acceptance criteria:**
1. Synthetic-list unit tests: `as_of` 2 days before a date ⇒ 2; after last known ⇒ None; sparse-history ⇒ None.
2. Empty yfinance response ⇒ gate skipped downstream, no crash.

**Estimate:** M. **Dependencies:** E2.4, E1.1.

---

## EPIC E6 — Backtest Engine (`scanner/backtest.py`)

### E6.1 — Signal-generation loop
**Description:** `generate_signals(universe, start, end, strategy, capture_near_misses=1) -> list[Signal]`. Trading days = the cached SPY index between start/end (never an invented calendar). Per ticker: load the FULL cached frame once, then per date `df.loc[:d]` slice (≥220 rows required, mirroring current minimums) → `make_context`-equivalent built from pre-loaded frames (add an internal `make_context_from_frames(...)` so the loop never touches disk per date) → `evaluate` → `attach_risk`. Qualifying results → `Signal(date, ticker, strategy, score, confidence, stop, target, atr, qualified=True)`; near-misses failing ≤ `capture_near_misses` gates recorded with `qualified=False, failed_gates=[...]`. Progress via tqdm if importable, else counter.

**Acceptance criteria:**
1. 3-ticker/30-day synthetic fixture: signals fire on exactly the hand-checked dates (engineer one fixture to qualify on a known date — extend E0.2 with a time-located setup).
2. No network and no per-date disk reads inside the loop (mocks raise).
3. 100 tickers × 1 year < 10 min on a laptop; if missed, profile and report before optimizing.

**Estimate:** L. **Dependencies:** E2.4, E4.1, E3.2.

### E6.2 — Backtest CLI + run artifacts
**Description:** `scan.py backtest --strategy pullback --universe sp600.txt --start 2023-01-01 --end 2025-12-31 --out runs/pb_23_25/ [--earnings-gate on|off] [--capture-near-misses 1] [--time-stop 10] [--entry next_open|signal_close]`. Writes `signals.parquet`, `trades.parquet` (E7), `report.md`/`report.json` (E8), `run_meta.json` (args, git hash if available, counts, wall time, per-gate skip rates).

**Acceptance criteria:**
1. Fixture run produces all five files with internally consistent counts.
2. Re-run with identical args ⇒ byte-identical `signals.parquet` (determinism).

**Estimate:** M. **Dependencies:** E6.1, E7.1, E8.1.

### E6.3 — Bias disclosure block
**Description:** Hard-coded "Known biases" section in every report: (a) survivorship — universe is currently-listed names, results optimistic; (b) quality fields are present-day values applied historically (look-ahead); (c) earnings-gate skip rate (computed from signals' skipped_gates). (c) computed; (a)/(b) static text.
**Acceptance criteria:** 1. Present in every report; skip-rate matches hand count on fixture. **Estimate:** S. **Dependencies:** E8.1.

---

## EPIC E7 — Trade Simulator (`scanner/simulate.py`)

### E7.1 — `simulate_trades(signals, bars_provider, entry="next_open", time_stop=10) -> list[Trade]`
**Description:** Replaces and upgrades the inline logic of legacy `backtest_setups` (swing_scanner lines 858–880). Per signal:
- Entry: open of the first bar AFTER signal date. Entry-gap guards: open ≥ target ⇒ skip (`skipped_gap=True`); open ≤ stop ⇒ skip; no next bar ⇒ `incomplete=True`, excluded from metrics.
- Exit per subsequent bar, in order: Low ≤ stop ⇒ exit AT stop price; same-bar Low ≤ stop AND High ≥ target ⇒ PESSIMISTIC stop-out, `ambiguous_bar=True`; High ≥ target ⇒ exit at target; `time_stop` sessions elapsed ⇒ exit at that close.
- `Trade(ticker, signal_date, entry_date, entry_px, exit_date, exit_px, exit_reason, r_multiple, holding_days, score, confidence, strategy, qualified, flags)`; `r = (exit−entry)/(entry−stop)`.
Stops/targets come FROM the signal (E4.1) — never recomputed here.

**Acceptance criteria:**
1. Mandatory fixture set, written FIRST: clean target hit, clean stop hit, time-stop exit, gap-skip up, gap-skip down, ambiguous bar — each with hand-computed exit price and R asserted.
2. Stop-out at stop price ⇒ r exactly −1.0.
3. `entry_date > signal_date` for every trade.
4. Ambiguous-bar share is surfaced to E8; >15% triggers a report warning ("daily bars too coarse for this stop distance").

**Estimate:** M/L. **Dependencies:** E6.1 (signal shape), E4.1.

---

## EPIC E8 — Metrics & Attribution (`scanner/report.py`)

### E8.1 — Core metrics
**Description:** From trades: count, win rate, avg win R / avg loss R, expectancy (R), median holding days, exit-reason breakdown, max drawdown of cumulative-R curve, monthly signal counts, ambiguous/gap-skip shares. Render `report.md` (summary table + monthly table) and `report.json`.
**Acceptance criteria:** 1. Hand-built 6-trade fixture (3×+2R, 3×−1R) ⇒ 50% win rate, +0.5R expectancy, hand-verified drawdown. 2. Zero trades ⇒ graceful report, exit 0. **Estimate:** M. **Dependencies:** E7.1.

### E8.2 — Score & confidence buckets
**Description:** Bucket by score (constants: 40–54, 55–69, 70–84, 85+) AND by confidence (LOW/MEDIUM/HIGH from E4.3) — confidence is the more decision-relevant cut for István's workflow. Per bucket: n, win rate, expectancy. Verdict line: monotonic / non-monotonic across buckets with n ≥ 20; smaller buckets labeled "insufficient n".
**Acceptance criteria:** 1. Monotonic fixture verdict correct. 2. n=19 bucket excluded from verdict. **Estimate:** S. **Dependencies:** E8.1.

### E8.3 — Gate attribution via near-misses
**Description:** Simulate near-miss signals (qualified=False) in a separate pass; per gate G: n(failed only G), expectancy(failed only G) vs expectancy(qualified), delta. Interpretation per gate: |delta| small with n ≥ 30 ⇒ "no measurable value in this sample". Near-misses NEVER enter E8.1 headline numbers. This is the deliverable that decides which of the 7 pullback enhancements (and E3.3's proposed breakout gates) earn their keep.
**Acceptance criteria:** 1. Fixture where NR7-only failures match qualified expectancy ⇒ delta≈0 with correct interpretation. 2. n<30 ⇒ "insufficient n". 3. Headline metrics unchanged by near-miss inclusion. **Estimate:** M. **Dependencies:** E6.1, E7.1.

---

## EPIC E9 — Persistence Layer & Live Signal Journal (`scanner/store_db.py`, `scanner/journal.py`)

> **Storage decision (István, 2026-06-11):** the batch engine stays Python and persists everything to ONE database so the website (E12) has a single read source. SQLite is the default (zero-ops, single-user, localhost); the schema and access layer must stay swappable to Postgres later (the independent-income/SaaS path) by confining all SQL to `store_db.py` and using only portable types. The parquet OHLCV cache (E1) stays as-is — it's the engine's working cache, not application state, and the website never reads it. Backtest *artifacts* (E6.2), currently loose files, are additionally ingested into the DB by E9.4 so reports are queryable.

### E9.1 — Persistence layer + signal schema (`scanner/store_db.py`)
**Description:** Single module owning the DB connection and ALL SQL. Default `data/scanner.db` (rename from `journal.db` — this DB now holds more than the journal; keep a one-line note for anyone who had the old name). No ORM; thin functions returning dataclasses/dicts. Tables (portable types only — `TEXT/INTEGER/REAL`, ISO-8601 date strings, no SQLite-specific column types):
- `signals`: Signal fields (date, ticker, strategy, score, confidence, stop, target, atr, qualified) + `source ("live"|"backtest")`, `run_id`, `created_at`, nullable outcome columns (`outcome_checked_at, entry_px, exit_px, exit_reason, r_multiple, holding_days, flags`). Unique key `(date, ticker, strategy, source, run_id)` — note `run_id` is part of the key so the same date/ticker can exist across backtest runs; for live, `run_id` is the scan timestamp. INSERT OR IGNORE.
- `runs`: `run_id (pk), kind ("scan"|"backtest"), strategy, universe, params_json, started_at, finished_at, signal_count`.
- `backtest_reports`: `run_id (fk), metrics_json, biases_json` — the E8 numbers, queryable (E9.4).

Provide a `migrate()` that creates tables if missing and records a `schema_version`. Keep `journal.py` as the higher-level workflow module (writer/resolver/compare) calling into `store_db.py`.

**Acceptance criteria:**
1. `migrate()` idempotent; opening an existing correct DB is a no-op; `schema_version` row present.
2. All SQL string literals live in `store_db.py` (grep: no `SELECT`/`INSERT` elsewhere).
3. Round-trip unit test: write a Signal, read it back as the dataclass unchanged.

**Estimate:** M. **Dependencies:** E4.5, E6.1 (Signal shape).

### E9.2 — Live signal writer
**Description:** `scan.py scan` writes qualifying live signals via `store_db` by default (`--no-journal` opt-out), `source="live"`, `run_id`=scan timestamp, recording a `runs` row. (Was E9.1 in the prior revision.)
**Acceptance criteria:** 1. Same-evening double scan ⇒ no duplicate signals (different `run_id` but de-duped on the natural key within a day — define: for live, collapse `run_id` to the trading date so re-scans don't double-insert). 2. `unresolved_live_signals()` returns only NULL-outcome live rows. **Estimate:** S/M. **Dependencies:** E9.1.

### E9.3 — `scan.py journal resolve`
**Description:** For unresolved live signals ≥1 trading day old: `refresh_ticker`, feed real subsequent bars to `simulate_trades` (E7 — import it; zero duplicated exit logic), write outcome columns. In-flight signals stay unresolved. Idempotent. Summary: resolved / open / failures.
**Acceptance criteria:** 1. Imports E7's simulator (grep-verified single implementation). 2. Time-stop-not-elapsed signal stays open. 3. Second run is a no-op. **Estimate:** M. **Dependencies:** E9.1, E7.1, E1.1.

### E9.4 — Ingest backtest artifacts into the DB
**Description:** `scan.py backtest` additionally writes its signals to `signals` (`source="backtest"`, real `run_id`), the run to `runs`, and the E8 metrics/biases to `backtest_reports`. The loose `report.md`/`.json`/`signals.parquet` files (E6.2) remain for human/CLI use, but the DB becomes the website's source of truth. Add `store_db.get_backtest_runs()` / `get_run_report(run_id)`.
**Acceptance criteria:** 1. A fixture backtest run is fully reconstructable from the DB (signals + metrics) without reading the parquet/md files. 2. Counts in `runs.signal_count` match rows in `signals` for that `run_id`. **Estimate:** S/M. **Dependencies:** E9.1, E6.2, E8.1.

### E9.5 — `scan.py journal compare --backtest <run_id>`
**Description:** Live (resolved) vs a stored backtest run's expectancy/win-rate per strategy, n for each, "live n < 30 — not yet statistically meaningful" warning. Now reads both sides from the DB (was: read backtest from a run folder). The overfitting detector.
**Acceptance criteria:** 1. Warning boundary verified at n=29 vs 30. 2. Pulls backtest metrics from `backtest_reports`, not files. **Estimate:** S. **Dependencies:** E9.4, E8.1.

---

## EPIC E10 — Universe (`scanner/universe.py`)

### E10.1 — Builder + audit
**Description:** `scan.py universe build --index {sp500,sp400,sp600} --out universes/sp600.txt` — scrape the Wikipedia constituents table via `pandas.read_html` (select the table containing a Symbol/Ticker column; normalize dots→dashes, BRK.B→BRK-B; one ticker per line; generated-on header). `scan.py universe audit --file F` — flags tickers whose history can't be fetched (uses `refresh_universe`'s failure report). The breakout_filter docstring's IWM-holdings-CSV note (lines 13–16) becomes a documented alternative: `--from-csv holdings.csv --ticker-col Ticker`.
**Acceptance criteria:** 1. sp600 build ⇒ 590–610 normalized lines. 2. Audit flags a planted dead ticker; per-ticker errors non-fatal. **Estimate:** M. **Dependencies:** E1.1.

### E10.2 — Default universe & sample cleanup
**Description:** `SAMPLE_UNIVERSE` (15 names duplicated in both filter files) moves to `universes/sample.txt`; `scan.py scan` without a universe arg uses it with the existing "demo" warning text. ETFs (the old Tier 3 concept) get `universes/etfs.txt` maintained by hand.
**Acceptance criteria:** 1. No ticker-list constants in package modules (grep). **Estimate:** XS. **Dependencies:** E4.5.

---

## EPIC E11 — Test Suite Consolidation & CI

### E11.1 — Full pytest suite
**Description:** Consolidate: E0 golden masters (now regression tests for the package), per-helper unit tests (`_nr7`, `_pocket_pivot`, `_bullish_reversal_candle`, `_rs_metrics`, weekly resample, ADV, position sizing, calendar, earnings parser), E7 simulator fixtures, E8 metric fixtures. Autouse fixture monkeypatches yfinance to raise ⇒ proves the only network seams are the two store modules. Target `pytest -q` < 30s offline; pytest-cov informational report, ≥80% lines over `scanner/core.py`, `strategies/`, `simulate.py`, `backtest.py`.
**Acceptance criteria:** 1. Single command, green, offline, <30s. 2. Coverage threshold met or shortfall documented. **Estimate:** M (most tests already exist from earlier ACs; this is consolidation). **Dependencies:** everything above.

---

## EPIC E12 — Website (Node/Express API + Angular SPA, localhost)

> **Architecture decision (István, 2026-06-11):** the Python package stays the headless batch engine; it runs manually or as a future scheduled job and writes to the E9 database. The website is a SEPARATE read-mostly application: an Express (Node, plain JS, nothing fancy) API that reads `data/scanner.db`, with an Angular SPA frontend. For now everything runs on localhost; deployment is explicitly out of scope. The web layer NEVER imports Python or pandas — it reads the database the engine produces. The one exception (on-demand diagnose/backtest triggering) is handled by E12.6 via a job row the Python engine polls, so the API still never executes Python directly.
>
> **Daily workflow the site must support** (this drives the menu): evening → run/refresh has already happened in the engine → (1) review tonight's qualified candidates, (2) drill into a candidate's full gate diagnosis + chart context + position size, (3) record which setups you actually took, (4) next morning → see resolved outcomes of prior signals, (5) periodically → check backtest reports and the live-vs-backtest calibration so you trust the scores. Menu items map 1:1 to these.

### E12.1 — Express API scaffold + read-only DB access
**Description:** `web/api/` — Express app, plain JS, `better-sqlite3` (synchronous, simplest for a local single-user read path) opening `data/scanner.db` READ-ONLY. Config via `.env` (`DB_PATH`, `PORT`). Structure: `routes/`, `db/` (all SQL here, mirroring the Python `store_db` discipline — one place owns queries), `server.js`. Health route `GET /api/health` returns `{status, db_path, schema_version, last_scan_run}`. CORS enabled for the Angular dev origin (localhost:4200). No write routes in this task.
**Acceptance criteria:** 1. `npm start` serves `/api/health` reading the real schema_version written by E9.1. 2. Opening a missing DB ⇒ clear 503 with a "run the scanner first" message, not a crash. 3. All SQL confined to `db/` (grep). **Estimate:** M. **Dependencies:** E9.1.

### E12.2 — Read API endpoints (the data the SPA needs)
**Description:** Read routes over the E9 schema:
- `GET /api/signals/latest?strategy=&min_score=&confidence=` — most recent live scan's qualified signals (the candidate list), with stop/target/RR/atr/confidence/ath_zone.
- `GET /api/signals/:id` — one signal with every stored field (feeds the diagnosis view; the per-gate pass/fail/skip detail must be persisted for this — see E12.2a).
- `GET /api/signals/history?from=&to=&status=open|resolved&strategy=` — journal list.
- `GET /api/runs?kind=scan|backtest` and `GET /api/runs/:run_id` — run metadata + (for backtests) the stored report metrics/biases.
- `GET /api/journal/compare?backtest_run=:id` — the E9.5 numbers as JSON.
- `GET /api/stats/summary` — counts for the dashboard (open positions, signals tonight, last scan time, current regime).

**E12.2a (sub-task, touches Python):** the diagnosis view needs the full gate log per signal, which the engine currently only prints. Persist it: add a `gate_detail_json` column to `signals` (list of `{name, status: pass|fail|skip, detail}`) populated by `GateLog` at scan time. Small change in `store_db` + the scan writer (E9.2). Without this, E12.4 can only show pass/fail counts, not the line-by-line log that makes diagnose useful.

**Acceptance criteria:** 1. Each endpoint returns shaped JSON against a seeded test DB (seed fixture = a few rows written via the Python `store_db`, proving schema compatibility across the language boundary). 2. Filters work (param combinations tested). 3. `gate_detail_json` round-trips Python→DB→API for one signal. **Estimate:** M/L. **Dependencies:** E12.1, E9.1, E9.4, E2.1 (GateLog detail).

### E12.3 — Angular app shell + navigation
**Description:** `web/ui/` — Angular SPA (CLI default tooling, nothing exotic), an `ApiService` wrapping the E12.2 endpoints, a layout with the workflow-driven left menu:
1. **Dashboard** — tonight's summary, market regime banner, quick counts, open positions at a glance.
2. **Candidates** — tonight's qualified signals (the core screen), filterable by strategy/score/confidence, sortable, row → Diagnosis.
3. **Diagnosis** — single-name deep view (gate log, levels, sizing, chart context).
4. **Journal** — signal history with open/resolved status and outcomes.
5. **Backtests** — run list → report detail.
6. **Calibration** — live-vs-backtest comparison (the trust screen).
Routing + empty states for each. Plain styling; this is a personal tool, not a product (yet).
**Acceptance criteria:** 1. `ng serve` runs on :4200, all six routes reachable, menu reflects the workflow order. 2. Dashboard renders live data from `/api/stats/summary` and `/api/signals/latest`. 3. Graceful empty states when the DB has no data yet. **Estimate:** M/L. **Dependencies:** E12.2.

### E12.4 — Candidates + Diagnosis views
**Description:** **Candidates:** table of tonight's qualified setups — ticker, strategy, score, confidence, entry/stop/target, RR, ATH zone, sector — with the filters from E12.2 and a one-click row into Diagnosis. **Diagnosis:** the decision screen — the full persisted gate log (✓/✗/– with details, grouped by section as in the CLI), price levels, the E4.4 position size for the user's account params (entered in the UI, sent as query params — no secrets stored), and risk/reward. A lightweight price/indicator chart is OPTIONAL here and split into E12.7 to keep this task shippable.
**Acceptance criteria:** 1. Candidate row → Diagnosis shows the same gate verdicts the CLI `--ticker` diagnose would print for that signal (compare against a seeded row). 2. Changing account-size/risk inputs updates the displayed share count live. **Estimate:** M. **Dependencies:** E12.3, E12.2a.

### E12.5 — Journal, Backtests, Calibration views
**Description:** **Journal:** filterable signal history, open vs resolved, outcome (exit reason, R) for resolved rows. **Backtests:** list of runs (date, strategy, universe, expectancy, win rate) → detail page rendering the stored E8 metrics, score/confidence buckets, gate-attribution table, and the bias-disclosure block. **Calibration:** the E9.5 live-vs-backtest table with the n<30 warning surfaced prominently.
**Acceptance criteria:** 1. Backtest detail renders metrics from `/api/runs/:id` matching the CLI `report.md` numbers for the same run. 2. Calibration shows the warning when live n<30. **Estimate:** M. **Dependencies:** E12.3, E12.2.

### E12.6 — On-demand actions via job queue (the only write path)
**Description:** For "diagnose this ticker now" / "kick off a backtest" without the API executing Python: a `jobs` table in `data/scanner.db` (`id, kind, params_json, status (queued|running|done|error), result_ref, created_at, finished_at`). Express exposes `POST /api/jobs` (enqueue) + `GET /api/jobs/:id` (poll). The Python side gets `scan.py worker` — a loop (or single `--once` pass for manual use) that claims queued jobs, runs the corresponding engine function, writes results back to the DB, flips status. This keeps the clean language boundary: Express only ever touches the DB; Python owns all computation. Mark clearly as OPTIONAL/last — the core workflow (E12.1–E12.5) works fully read-only, since the engine already produces signals on its schedule.
**Acceptance criteria:** 1. Enqueue a diagnose job via API → run `scan.py worker --once` → job flips to done with a referenceable result → API returns it. 2. Worker is idempotent and crash-safe (a claimed-but-unfinished job is re-claimable). 3. Express has no dependency on Python being running for read routes. **Estimate:** M/L. **Dependencies:** E12.2, E9.1, E4.5.

### E12.7 — OPTIONAL: price/indicator chart in Diagnosis
**Description:** Client-side candlestick + SMA/EMA overlay and the computed stop/target/support levels, in the Diagnosis view. Needs an OHLCV read endpoint: either a new `GET /api/ohlcv/:ticker` (requires exporting recent bars from the parquet cache into the DB or a small read-only parquet reader in Node — decide at implementation time; exporting a recent window to a `bars` table during scan is the cleaner boundary) or deferring until needed. Charting lib left to implementer (lightweight-charts is a reasonable default). Genuinely optional — the gate log + levels already make the decision.
**Acceptance criteria:** 1. Chart renders bars for a seeded ticker with stop/target lines. **Estimate:** M. **Dependencies:** E12.4.

---

## Appendix A — Divergences between the three files (resolved decisions; implementers follow these, do not re-litigate)

| Topic | pullback_filter.py | breakout_filter.py | swing_scanner.py | DECISION |
|---|---|---|---|---|
| Pullback RSI gate | 40–60 (line 73) | — | 25–55 effective (lines 972–974) | **40–60** (filter wins) |
| Pullback "near support" | multi-candidate ≤2.5% (lines 473–507) | — | EMA20 dist <5% gate | **multi-candidate** |
| Weekly trend MA | 30-week (line 92) | — | 10-week (line 685) | **30-week** |
| Weekly missing-data default | fail | — | pass ("benefit of doubt", line 700) | **SKIP** (E2.2c) |
| Earnings unknown | pass (999 sentinel) | no gate | no gate | **SKIP** (E2.2a) |
| Breakout earnings gate | gate exists (7d buffer) | none | none | **ADD to breakout** — approved by István 2026-06-11 (E3.3); RS/sector/weekly deferred to E3.4 |
| Volume baseline (breakout) | — | SMA50 vol (line 111) | SMA20 vol | **SMA50** |
| History period | 1y, ≥220 rows | 1y, ≥220 rows | 3mo, ≥50 rows | **full cache, ≥220 rows** |
| Stops/targets | none | none | EMA20−ATR / high20−0.5·ATR + 5-method targets | **port swing_scanner's** (E4.1) |
| Market regime | none | none | display + confidence input | **port, display-only** (E4.2) |
| Backtest | none | none | crude inline (lines 817–920), conditions contradict pullback_filter | **delete; E6/E7 replace** |
| Universe | bring-your-own + sample | bring-your-own + sample | TIER0–3 static lists | **bring-your-own; tiers deleted** |
| Sizing | none | none | fixed $650 (line 1377) | **risk-based** (E4.4) |

## Appendix B — Sprint slicing
- **Sprint 1:** E0 (all), E1.1–E1.3 — fixtures, golden masters, data layer. No behavior changes yet.
- **Sprint 2:** E2 (all), E3.1–E3.3 — the purity refactor, breakout parity, and the approved earnings gate. Riskiest work; golden masters are the safety net.
- **Sprint 3:** E4 (all) — targets/stops, regime, confidence, sizing, unified CLI, legacy retirement. Scanner is now a single coherent tool.
- **Sprint 4:** E5.2–E5.3, E6, E7, E8 — first real backtest numbers + gate attribution.
- **Sprint 5:** E9 (persistence + journal), E10, E11, E3.4 deferred-gate review — single DB, universe, consolidation.
- **Sprint 6 (website):** E12.1–E12.5 — Express read API + Angular workflow SPA on localhost. E12.6 (job queue) and E12.7 (chart) are optional follow-ups once the read-only workflow is in daily use.

## Definition of Done (every task)
- All acceptance criteria demonstrably met (tests or reproducible commands cited in the summary).
- Golden masters green, or each diff enumerated with justification.
- No network I/O outside `data_store.py`/`earnings_store.py`; no wall-clock in evaluation logic.
- `pytest -q` green offline.