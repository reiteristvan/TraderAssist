# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2026-01-01 → 2026-06-25
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 807f094

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 198 |
| Win rate | 47.0% |
| Avg win (R) | 1.72 |
| Avg loss (R) | -0.97 |
| Expectancy (R) | 0.290 |
| Median hold (days) | 4 |
| Max drawdown (R) | 48.00 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 0 | — | — | insufficient n |
| 70–84 | 7 | 71.4% | 0.796 | insufficient n |
| 85–100 | 189 | 46.0% | 0.273 | ok |

*Score bucket verdict: insufficient data for verdict*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 2 | 100.0% | 0.432 | insufficient n |
| MEDIUM | 142 | 44.4% | 0.224 | ok |
| HIGH | 54 | 51.9% | 0.459 | ok |

*Confidence bucket verdict: monotonically increasing*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
| 2026-01 | 49 |
| 2026-02 | 18 |
| 2026-03 | 25 |
| 2026-04 | 13 |
| 2026-05 | 92 |
| 2026-06 | 16 |


## Exit Reason Breakdown

| Reason | Count |
|--------|-------|
| stop | 99 |
| target | 55 |
| time_stop | 44 |
| gap_skip_down | 13 |
| gap_skip_up | 2 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Verdict |
|------|---------------|----------------|----------------|------|---------|
| 200-MA distance in range | 48 | -0.071 | 0.290 | -0.362 | questionable gate value (near-misses match or beat qualified) |
| ADX(14) trend strength | 129 | 0.721 | 0.290 | 0.431 | positive gate value (near-misses underperform qualified) |
| At a logical support level | 65 | -0.272 | 0.290 | -0.562 | questionable gate value (near-misses match or beat qualified) |
| Debt/equity acceptable | 30 | -0.101 | 0.290 | -0.391 | questionable gate value (near-misses match or beat qualified) |
| Earnings clear | 16 | -0.211 | 0.290 | -0.501 | insufficient n |
| Liquidity | 8 | 0.504 | 0.290 | 0.213 | insufficient n |
| Market cap in range | 64 | -0.140 | 0.290 | -0.430 | questionable gate value (near-misses match or beat qualified) |
| Near 52w high in last 60d | 53 | 0.027 | 0.290 | -0.264 | questionable gate value (near-misses match or beat qualified) |
| Profitable | 1 | 2.023 | 0.290 | 1.733 | insufficient n |
| Pullback depth | 92 | 0.467 | 0.290 | 0.177 | positive gate value (near-misses underperform qualified) |
| Pullback duration 1d | 4 | 0.329 | 0.290 | 0.039 | insufficient n |
| Pullback duration 21d | 8 | -0.224 | 0.290 | -0.514 | insufficient n |
| Pullback duration 22d | 4 | -0.146 | 0.290 | -0.436 | insufficient n |
| Pullback duration 23d | 4 | 1.401 | 0.290 | 1.111 | insufficient n |
| Pullback duration 24d | 5 | 0.211 | 0.290 | -0.080 | insufficient n |
| Pullback duration 25d | 3 | -0.154 | 0.290 | -0.444 | insufficient n |
| Pullback duration 26d | 3 | 0.380 | 0.290 | 0.090 | insufficient n |
| Pullback duration 27d | 3 | 0.541 | 0.290 | 0.251 | insufficient n |
| Pullback duration 29d | 2 | -0.044 | 0.290 | -0.335 | insufficient n |
| Pullback duration 2d | 10 | 0.285 | 0.290 | -0.005 | insufficient n |
| Pullback duration 30d | 1 | -1.000 | 0.290 | -1.290 | insufficient n |
| Pullback duration 32d | 2 | -0.125 | 0.290 | -0.415 | insufficient n |
| Pullback duration 33d | 3 | -0.394 | 0.290 | -0.684 | insufficient n |
| Pullback duration 34d | 1 | -1.000 | 0.290 | -1.290 | insufficient n |
| Pullback duration 35d | 2 | -0.265 | 0.290 | -0.555 | insufficient n |
| Pullback duration 38d | 1 | -1.000 | 0.290 | -1.290 | insufficient n |
| Pullback duration 39d | 2 | 0.155 | 0.290 | -0.135 | insufficient n |
| RSI(14) reset | 18 | -0.113 | 0.290 | -0.404 | insufficient n |
| Relative strength vs SPY | 4 | -0.225 | 0.290 | -0.515 | insufficient n |
| SMA50 rising (20 sessions) | 5 | -0.395 | 0.290 | -0.685 | insufficient n |
| Sector (XLB) above 50MA | 3 | -1.000 | 0.290 | -1.290 | insufficient n |
| Sector (XLC) above 50MA | 4 | -0.754 | 0.290 | -1.044 | insufficient n |
| Sector (XLE) above 50MA | 11 | 0.802 | 0.290 | 0.512 | insufficient n |
| Sector (XLF) above 50MA | 51 | -0.818 | 0.290 | -1.109 | questionable gate value (near-misses match or beat qualified) |
| Sector (XLI) above 50MA | 6 | -1.000 | 0.290 | -1.290 | insufficient n |
| Sector (XLK) above 50MA | 9 | -0.446 | 0.290 | -0.736 | insufficient n |
| Sector (XLP) above 50MA | 14 | -0.747 | 0.290 | -1.038 | insufficient n |
| Sector (XLRE) above 50MA | 10 | 1.767 | 0.290 | 1.476 | insufficient n |
| Sector (XLV) above 50MA | 11 | -0.805 | 0.290 | -1.096 | insufficient n |
| Sector (XLY) above 50MA | 19 | -0.660 | 0.290 | -0.950 | insufficient n |
| Uptrend (SMA50 > SMA200) | 9 | 0.706 | 0.290 | 0.415 | insufficient n |
| Volume contraction | 397 | 0.501 | 0.290 | 0.210 | positive gate value (near-misses underperform qualified) |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.2% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 7.0% of simulated entries were skipped due to the opening price being outside the stop/target range.
