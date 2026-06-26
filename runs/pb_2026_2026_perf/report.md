# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2026-01-01 → 2026-06-25
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: b1ac62e

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 199 |
| Win rate | 46.7% |
| Avg win (R) | 1.71 |
| Avg loss (R) | -0.97 |
| Expectancy (R) | 0.283 |
| Median hold (days) | 4 |
| Max drawdown (R) | 49.00 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 0 | — | — | insufficient n |
| 70–84 | 7 | 71.4% | 0.796 | insufficient n |
| 85–100 | 191 | 45.5% | 0.259 | ok |

*Score bucket verdict: insufficient data for verdict*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 2 | 100.0% | 0.432 | insufficient n |
| MEDIUM | 143 | 44.1% | 0.214 | ok |
| HIGH | 54 | 51.9% | 0.459 | ok |

*Confidence bucket verdict: monotonically increasing*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
| 2026-01 | 49 |
| 2026-02 | 18 |
| 2026-03 | 25 |
| 2026-04 | 13 |
| 2026-05 | 93 |
| 2026-06 | 16 |


## Exit Reason Breakdown

| Reason | Count |
|--------|-------|
| stop | 100 |
| target | 55 |
| time_stop | 44 |
| gap_skip_down | 13 |
| gap_skip_up | 2 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Verdict |
|------|---------------|----------------|----------------|------|---------|
| 200-MA distance in range | 48 | -0.071 | 0.283 | -0.354 | questionable gate value (near-misses match or beat qualified) |
| ADX(14) trend strength | 131 | 0.715 | 0.283 | 0.432 | positive gate value (near-misses underperform qualified) |
| At a logical support level | 66 | -0.283 | 0.283 | -0.566 | questionable gate value (near-misses match or beat qualified) |
| Debt/equity acceptable | 30 | -0.101 | 0.283 | -0.384 | questionable gate value (near-misses match or beat qualified) |
| Earnings clear | 16 | -0.211 | 0.283 | -0.494 | insufficient n |
| Liquidity | 8 | 0.504 | 0.283 | 0.221 | insufficient n |
| Market cap in range | 63 | -0.126 | 0.283 | -0.409 | questionable gate value (near-misses match or beat qualified) |
| Near 52w high in last 60d | 54 | 0.008 | 0.283 | -0.275 | questionable gate value (near-misses match or beat qualified) |
| Profitable | 1 | 2.023 | 0.283 | 1.740 | insufficient n |
| Pullback depth | 92 | 0.467 | 0.283 | 0.184 | positive gate value (near-misses underperform qualified) |
| Pullback duration 1d | 4 | 0.329 | 0.283 | 0.046 | insufficient n |
| Pullback duration 21d | 8 | -0.224 | 0.283 | -0.507 | insufficient n |
| Pullback duration 22d | 5 | -0.166 | 0.283 | -0.449 | insufficient n |
| Pullback duration 23d | 4 | 1.401 | 0.283 | 1.118 | insufficient n |
| Pullback duration 24d | 5 | 0.211 | 0.283 | -0.072 | insufficient n |
| Pullback duration 25d | 3 | -0.154 | 0.283 | -0.437 | insufficient n |
| Pullback duration 26d | 3 | 0.380 | 0.283 | 0.097 | insufficient n |
| Pullback duration 27d | 3 | 0.541 | 0.283 | 0.258 | insufficient n |
| Pullback duration 29d | 2 | -0.044 | 0.283 | -0.327 | insufficient n |
| Pullback duration 2d | 10 | 0.285 | 0.283 | 0.003 | insufficient n |
| Pullback duration 30d | 1 | -1.000 | 0.283 | -1.283 | insufficient n |
| Pullback duration 32d | 1 | -1.000 | 0.283 | -1.283 | insufficient n |
| Pullback duration 33d | 3 | -0.394 | 0.283 | -0.677 | insufficient n |
| Pullback duration 34d | 1 | -1.000 | 0.283 | -1.283 | insufficient n |
| Pullback duration 35d | 2 | -0.265 | 0.283 | -0.548 | insufficient n |
| Pullback duration 38d | 1 | -1.000 | 0.283 | -1.283 | insufficient n |
| Pullback duration 39d | 2 | 0.155 | 0.283 | -0.128 | insufficient n |
| RSI(14) reset | 18 | -0.113 | 0.283 | -0.396 | insufficient n |
| Relative strength vs SPY | 3 | 0.109 | 0.283 | -0.174 | insufficient n |
| SMA50 rising (20 sessions) | 6 | 0.023 | 0.283 | -0.259 | insufficient n |
| Sector (XLB) above 50MA | 3 | -1.000 | 0.283 | -1.283 | insufficient n |
| Sector (XLC) above 50MA | 4 | -0.754 | 0.283 | -1.037 | insufficient n |
| Sector (XLE) above 50MA | 11 | 0.802 | 0.283 | 0.520 | insufficient n |
| Sector (XLF) above 50MA | 51 | -0.818 | 0.283 | -1.101 | questionable gate value (near-misses match or beat qualified) |
| Sector (XLI) above 50MA | 6 | -1.000 | 0.283 | -1.283 | insufficient n |
| Sector (XLK) above 50MA | 9 | -0.446 | 0.283 | -0.728 | insufficient n |
| Sector (XLP) above 50MA | 14 | -0.747 | 0.283 | -1.030 | insufficient n |
| Sector (XLRE) above 50MA | 10 | 1.767 | 0.283 | 1.484 | insufficient n |
| Sector (XLV) above 50MA | 10 | -0.786 | 0.283 | -1.069 | insufficient n |
| Sector (XLY) above 50MA | 19 | -0.660 | 0.283 | -0.943 | insufficient n |
| Uptrend (SMA50 > SMA200) | 10 | 0.949 | 0.283 | 0.666 | insufficient n |
| Volume contraction | 400 | 0.511 | 0.283 | 0.228 | positive gate value (near-misses underperform qualified) |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.2% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 7.0% of simulated entries were skipped due to the opening price being outside the stop/target range.
