# TraderAssist — Swing Scanner Reference

## What's built

All epics (E0–E12) are complete. The codebase is a working system, not a backlog.

```
scanner/
  data_store.py       # Parquet OHLCV cache — only module that imports yfinance for prices
  earnings_store.py   # Parquet earnings-date cache
  core.py             # GateLog, EvalContext, QualityInfo, run_scan, make_contexts, indicators
  targets.py          # stop/target engine, attach_risk
  regime.py           # market_regime, ath_zone, compute_confidence
  strategies/
    pullback.py       # evaluate() → PullbackResult
    breakout.py       # evaluate() → BreakoutResult
  backtest.py         # generate_signals() — historical signal loop
  simulate.py         # simulate_trades() — Signal → Trade
  report.py           # compute_metrics, render_report (E8)
  store_db.py         # ALL SQL; data/scanner.db; schema v10
  journal.py          # write_live_signals, resolve_open_signals, compare_with_backtest
  universe.py         # build_universe, audit_universe, load_universe_file
scan.py               # CLI: scan | refresh | backtest | journal | universe | worker

web/
  api/                # Express + better-sqlite3, read-only on scanner.db (port 3000)
  ui/                 # Angular SPA (port 4200)

universes/            # sp400.txt, sp500.txt, sp600.txt, sample.txt
data/
  scanner.db          # SQLite — signals, runs, backtest_reports, jobs, bars
  ohlcv/              # {TICKER}.parquet (tz-naive daily OHLCV)
  earnings/           # {TICKER}_earnings.parquet
legacy/               # retired swing_scanner.py, pullback_filter.py, breakout_filter.py
tests/
```

**Data flow:** `scan.py` writes to `data/scanner.db` → Express API reads it → Angular renders.
On-demand diagnose goes through the `jobs` table; `scan.py worker` processes it.
The Parquet cache is internal to the engine — the web layer never reads it directly
(exception: `bars` table in scanner.db is populated by `write_ohlcv_snapshot` for the chart).

## CLI quick reference

```bash
python scan.py scan --strategy {pullback,breakout,both} --file universes/sp500.txt
python scan.py scan --strategy pullback --ticker AAPL          # verbose diagnose
python scan.py scan --strategy both --file universes/sp_all.txt --allow-earnings
python scan.py refresh --file universes/sp500.txt
python scan.py refresh --file universes/sp500.txt --full       # force period=max
python scan.py backtest --strategy pullback --file universes/sp500.txt \
       --start 2023-01-01 --end 2025-12-31 --out runs/pb_23_25/
python scan.py journal resolve
python scan.py journal compare --backtest <run_id>
python scan.py universe build --index sp500 --out universes/sp500.txt
python scan.py worker --once
python winner_loser_split.py --run-id <run_id> --split 2024-01-01   # read-only train/holdout feature diagnostic
python exit_rule_sweep.py --run-dir runs/<dir> --mode all   # read-only exit-rule sweep (time stop / breakeven / fixed target)
```

## DB schema — scanner.db (v10)

`signals`: id, date, ticker, strategy, source, run_id, score, confidence, stop, target,
atr, qualified, failed_gates, close, gate_detail_json, ath_zone, outcome_checked_at,
entry_px, exit_px, exit_reason, r_multiple, holding_days, flags, created_at, notes,
target_r, target_atr, mae_r, mfe_r, post_stop_reached_target, post_stop_mfe_r,
industry_group, industry_momentum, industry_above_50ma, industry_rank_pct, rsi_entry,
rvol, pullback_depth_pct, pct_to_52w_high.

`runs`: run_id, kind, strategy, universe, params_json, started_at, finished_at, signal_count.

`backtest_reports`: run_id, metrics_json, biases_json.

`jobs`: id, kind, params_json, status, result_ref, created_at, finished_at.

`bars`: ticker, date, open, high, low, close, volume  ← OHLCV snapshot for chart (E12.7).

`schema_version`: version (current = 10).

## Global conventions

- **No `yf.` imports** outside `data_store.py` / `earnings_store.py`.
- **No `datetime.now()` / `pd.Timestamp.now()`** inside evaluation logic — use `ctx.as_of`.
- **Do not change gate thresholds or score formulas** without an explicit task. See Key Decisions below.
- `pytest -q` must stay green offline after every Python change.
- Web changes: `npm test` (API) and `ng test` (UI) must stay green.
- **Windows reserved names** (CON, PRN, AUX, NUL, COM1–9, LPT1–9) are filtered at universe
  load time and blocked in every `data_store` entry point — never create paths with these stems.

## Key design decisions (do not re-litigate without new data)

| Topic | Decision | Rationale |
|---|---|---|
| Pullback RSI | 40–60 | pullback_filter wins over swing_scanner (25–55) |
| Weekly MA | 30-week | pullback_filter wins over swing_scanner (10-week) |
| Weekly missing data | SKIP gate | neither fail nor auto-pass — data absence ≠ bearish |
| Earnings unknown | SKIP gate | unknown ≠ clear; don't silently pass |
| Breakout earnings gate | ACTIVE (7-day buffer) | approved 2026-06-11; tight breakout stop can't contain earnings gap |
| Volume baseline (breakout) | SMA50 | breakout_filter wins over swing_scanner (SMA20) |
| Minimum history | 220 rows | consistent across both strategies |
| Stop rules | Pullback: EMA20−ATR; Breakout: high20−0.5×ATR | ported from swing_scanner |
| Min stop-risk floor (close side) | `scanner/targets.py::apply_min_stop_floor` widens the published stop so `close − stop >= MIN_STOP_ATR_MULT × ATR` | quick-260819-g5h, approved 2026-08-19; makes the published stop executable at signal time |
| Min stop-risk floor (entry side) | `scanner/simulate.py::simulate_trades` re-applies the SAME `apply_min_stop_floor` helper against the entry open (next-open price), before computing risk; the resulting `effective_stop` drives stop-hit detection, the stop-out exit price, and every R metric (r_multiple, mae_r, mfe_r, target_r, post_stop_mfe_r) | quick-260819-ko0, approved 2026-08-19; an adverse overnight gap can re-collapse the risk denominator even after the close-side floor, so it must be re-applied at entry |
| Min stop-risk floor multiplier | `MIN_STOP_ATR_MULT = 0.5` lives in exactly one place (`scanner/targets.py`) and is reused by both floor applications — one house rule, not two independently-tuned constants | chosen for execution realism (a stop inside half an ATR can't survive normal intraday noise), NOT fitted to backtest expectancy; do not tune |
| Market regime | display + confidence input only — NOT a gate | |
| DB | SQLite (`data/scanner.db`), all SQL in `store_db.py` | swappable to Postgres by changing one module |
| Sizing | risk-based: `floor((account × risk%) / (entry − stop))` | replaces fixed $650 |

**Published-stop vs exit-price divergence (documented consequence of quick-260819-ko0):**
The `signals.stop` DB column intentionally keeps the published close-based stop — no new
column was added to record the entry-side widening (declined by design). For a stop-out trade,
`exit_px` is the entry-widened `effective_stop`, which can differ from `signals.stop`. For
roughly 14% of trades (measured on backtest run `038a385_2021-01-01_20260819_142048`) these two
values diverge, so `(entry_px − stop) / atr` computed directly from the raw `signals` columns
will still read below 0.5 even though the trade was simulated against a wider stop. **This is
expected behavior, not a bug.** The authoritative risk denominator for any trade is the one
implied by `exit_px` on a stop-out (`entry_px − exit_px`), not `entry_px − signals.stop`.

## Open item — E3.4 (deferred)

After the first real backtest run with enough signal history, produce a gate-attribution
note for the **RS vs SPY / sector strength / weekly trend** gates on the **breakout** strategy.
Use `scan.py backtest` output + `report.py`'s `gate_attribution()`. István decides which
(if any) to add. Approved gates become tasks tagged "changes trading logic."

## Running the stack

```bash
# Engine
pytest -q                              # must be green
python scan.py refresh --file universes/sample.txt
python scan.py scan --strategy both --file universes/sample.txt

# API
cd web/api && npm start                # http://localhost:3000/api/health

# UI
cd web/ui && ng serve                  # http://localhost:4200
```
