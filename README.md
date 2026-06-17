# TraderAssist — Swing Scanner

A modular swing-trading scanner for US equities. Detects pullback-to-support and breakout setups with a non-short-circuit gate engine, Parquet-cached OHLCV, and an offline-testable architecture.

## Usage

```bash
# Scan a single ticker (prints full gate log)
python scan.py scan --strategy pullback --ticker AAPL

# Scan from a file
python scan.py scan --strategy breakout --file universes/sp600.txt --csv results.csv

# Scan both strategies, show all (including near-misses)
python scan.py scan --strategy both --file universes/sample.txt --show-all

# Historical point-in-time scan
python scan.py scan --strategy pullback --file universes/sample.txt --date 2025-01-15

# Filter by confidence or score
python scan.py scan --strategy pullback --file universes/sp600.txt --high-only
python scan.py scan --strategy breakout --file universes/sp600.txt --min-score 60

# Allow earnings-proximity gate to be skipped (deliberate pre-earnings trades)
python scan.py scan --strategy both --file universes/sample.txt --allow-earnings

# Warm/refresh the Parquet cache
python scan.py refresh --file universes/sp600.txt
python scan.py refresh --file universes/sp600.txt --full  # force period=max re-fetch
```

## Architecture

```
scanner/                   # Python package
  data_store.py            # Parquet-cached OHLCV (the only yfinance-for-prices module)
  earnings_store.py        # (E5.3) cached earnings dates
  core.py                  # GateLog, EvalContext, QualityInfo, shared indicators, scan loop
  targets.py               # Stop/target engine (5-method confluence)
  regime.py                # Market regime, ATH zones, confidence scoring
  strategies/
    pullback.py            # evaluate() — pure pullback gate set
    breakout.py            # evaluate() — pure breakout gate set
  backtest.py              # (E6 stub)
  simulate.py              # (E7 stub)
  report.py                # (E8 stub)
  store_db.py              # (E9 stub)
  journal.py               # (E9 stub)
  universe.py              # (E10 stub)
scan.py                    # Unified CLI
universes/                 # Ticker lists (sample.txt, sp600.txt, ...)
legacy/                    # Retired source files (for reference only)
tests/                     # pytest suite — fully offline
```

**Data flow:** `scan.py` → `scanner.core.run_scan()` → per-ticker `evaluate()` → `attach_risk()` + `compute_confidence()` → DataFrame output.

## Development

```bash
pip install -r requirements.txt
pytest -q          # offline, <30s
make test          # equivalent
```

## Strategies

| Gate | Pullback | Breakout |
|---|---|---|
| Trend alignment (SMA50>SMA200) | ✓ | ✓ |
| Pullback depth 4–18% | ✓ | — |
| Near support (multi-candidate ≤2.5%) | ✓ | — |
| Volume contraction during pullback | ✓ | — |
| RSI 40–60 | ✓ | — |
| Near 52-week high (≥97%) | — | ✓ |
| Consolidation breakout | — | ✓ |
| Volume confirmation (≥1.5× SMA50) | — | ✓ |
| RSI 55–75 | — | ✓ |
| ADX ≥ 20 | ✓ | ✓ |
| BB squeeze (≤40th pctile) | — | ✓ |
| Liquidity ($5M ADV) | ✓ | ✓ |
| Earnings clear (>7 days) | ✓ | ✓ |
| Market cap $300M–$5B | ✓ | ✓ |
| Profitable | ✓ | ✓ |
| Debt/equity ≤ 150 | ✓ | ✓ |
| RS vs SPY ≥ 0.90 | ✓ | — |
| Sector strength | ✓ | — |
| Weekly 30MA alignment | ✓ | — |
| 200MA distance 3–30% | ✓ | — |

Missing-data gates (earnings, sector, weekly, market cap, debt/equity) are **skipped** rather than hard-failed, preserving `gates_total` integrity.
