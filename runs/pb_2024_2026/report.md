# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2024-01-01 → 2026-06-25
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 807f094

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 1623 |
| Win rate | 37.9% |
| Avg win (R) | 2.02 |
| Avg loss (R) | -0.94 |
| Expectancy (R) | 0.182 |
| Median hold (days) | 5 |
| Max drawdown (R) | 274.27 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 0 | — | — | insufficient n |
| 70–84 | 35 | 51.4% | 0.127 | ok |
| 85–100 | 1582 | 37.5% | 0.183 | ok |

*Score bucket verdict: monotonically increasing*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 12 | 50.0% | -0.078 | insufficient n |
| MEDIUM | 1002 | 41.2% | 0.256 | ok |
| HIGH | 609 | 32.2% | 0.065 | ok |

*Confidence bucket verdict: monotonically decreasing*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
| 2024-01 | 248 |
| 2024-02 | 37 |
| 2024-03 | 49 |
| 2024-04 | 86 |
| 2024-05 | 43 |
| 2024-06 | 27 |
| 2024-07 | 17 |
| 2024-08 | 237 |
| 2024-09 | 84 |
| 2024-10 | 98 |
| 2024-11 | 64 |
| 2024-12 | 249 |
| 2025-01 | 13 |
| 2025-02 | 20 |
| 2025-05 | 12 |
| 2025-06 | 14 |
| 2025-07 | 43 |
| 2025-08 | 27 |
| 2025-09 | 52 |
| 2025-10 | 34 |
| 2025-11 | 6 |
| 2025-12 | 21 |
| 2026-01 | 49 |
| 2026-02 | 18 |
| 2026-03 | 25 |
| 2026-04 | 13 |
| 2026-05 | 92 |
| 2026-06 | 16 |


## Exit Reason Breakdown

| Reason | Count |
|--------|-------|
| stop | 914 |
| target | 365 |
| time_stop | 344 |
| gap_skip_down | 65 |
| gap_skip_up | 6 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Verdict |
|------|---------------|----------------|----------------|------|---------|
| 200-MA distance in range | 369 | -0.112 | 0.182 | -0.294 | questionable gate value (near-misses match or beat qualified) |
| ADX(14) trend strength | 775 | 0.159 | 0.182 | -0.023 | no measurable value in this sample |
| At a logical support level | 524 | 0.059 | 0.182 | -0.123 | questionable gate value (near-misses match or beat qualified) |
| Debt/equity acceptable | 238 | -0.105 | 0.182 | -0.287 | questionable gate value (near-misses match or beat qualified) |
| Earnings clear | 102 | 0.100 | 0.182 | -0.082 | no measurable value in this sample |
| Liquidity | 107 | 0.279 | 0.182 | 0.097 | no measurable value in this sample |
| Market cap in range | 430 | -0.033 | 0.182 | -0.215 | questionable gate value (near-misses match or beat qualified) |
| Near 52w high in last 60d | 430 | -0.013 | 0.182 | -0.195 | questionable gate value (near-misses match or beat qualified) |
| Profitable | 23 | 0.803 | 0.182 | 0.621 | insufficient n |
| Pullback depth | 449 | -0.014 | 0.182 | -0.196 | questionable gate value (near-misses match or beat qualified) |
| Pullback duration 1d | 29 | -0.052 | 0.182 | -0.234 | insufficient n |
| Pullback duration 21d | 36 | -0.013 | 0.182 | -0.195 | questionable gate value (near-misses match or beat qualified) |
| Pullback duration 22d | 33 | -0.250 | 0.182 | -0.432 | questionable gate value (near-misses match or beat qualified) |
| Pullback duration 23d | 35 | -0.325 | 0.182 | -0.507 | questionable gate value (near-misses match or beat qualified) |
| Pullback duration 24d | 28 | -0.542 | 0.182 | -0.724 | insufficient n |
| Pullback duration 25d | 24 | -0.473 | 0.182 | -0.655 | insufficient n |
| Pullback duration 26d | 26 | -0.166 | 0.182 | -0.348 | insufficient n |
| Pullback duration 27d | 31 | -0.358 | 0.182 | -0.540 | questionable gate value (near-misses match or beat qualified) |
| Pullback duration 28d | 28 | -0.728 | 0.182 | -0.910 | insufficient n |
| Pullback duration 29d | 30 | -0.527 | 0.182 | -0.709 | questionable gate value (near-misses match or beat qualified) |
| Pullback duration 2d | 79 | 0.180 | 0.182 | -0.002 | no measurable value in this sample |
| Pullback duration 30d | 30 | -0.432 | 0.182 | -0.614 | questionable gate value (near-misses match or beat qualified) |
| Pullback duration 31d | 31 | -0.501 | 0.182 | -0.683 | questionable gate value (near-misses match or beat qualified) |
| Pullback duration 32d | 31 | -0.435 | 0.182 | -0.617 | questionable gate value (near-misses match or beat qualified) |
| Pullback duration 33d | 35 | 0.870 | 0.182 | 0.688 | positive gate value (near-misses underperform qualified) |
| Pullback duration 34d | 26 | 0.443 | 0.182 | 0.261 | insufficient n |
| Pullback duration 35d | 25 | 0.281 | 0.182 | 0.099 | insufficient n |
| Pullback duration 36d | 20 | -0.380 | 0.182 | -0.562 | insufficient n |
| Pullback duration 37d | 21 | 0.511 | 0.182 | 0.329 | insufficient n |
| Pullback duration 38d | 21 | -0.252 | 0.182 | -0.434 | insufficient n |
| Pullback duration 39d | 24 | 0.124 | 0.182 | -0.058 | insufficient n |
| RSI(14) reset | 131 | -0.039 | 0.182 | -0.221 | questionable gate value (near-misses match or beat qualified) |
| Relative strength vs SPY | 8 | 1.845 | 0.182 | 1.663 | insufficient n |
| SMA50 rising (20 sessions) | 29 | -0.283 | 0.182 | -0.465 | insufficient n |
| Sector (XLB) above 50MA | 27 | 0.371 | 0.182 | 0.189 | insufficient n |
| Sector (XLC) above 50MA | 12 | 0.179 | 0.182 | -0.003 | insufficient n |
| Sector (XLE) above 50MA | 38 | 0.121 | 0.182 | -0.061 | no measurable value in this sample |
| Sector (XLF) above 50MA | 72 | -0.796 | 0.182 | -0.978 | questionable gate value (near-misses match or beat qualified) |
| Sector (XLI) above 50MA | 56 | -0.458 | 0.182 | -0.640 | questionable gate value (near-misses match or beat qualified) |
| Sector (XLK) above 50MA | 33 | -0.180 | 0.182 | -0.362 | questionable gate value (near-misses match or beat qualified) |
| Sector (XLP) above 50MA | 44 | 0.193 | 0.182 | 0.011 | no measurable value in this sample |
| Sector (XLRE) above 50MA | 40 | 0.022 | 0.182 | -0.160 | questionable gate value (near-misses match or beat qualified) |
| Sector (XLU) above 50MA | 4 | -1.000 | 0.182 | -1.182 | insufficient n |
| Sector (XLV) above 50MA | 32 | 0.567 | 0.182 | 0.385 | positive gate value (near-misses underperform qualified) |
| Sector (XLY) above 50MA | 69 | 0.072 | 0.182 | -0.110 | questionable gate value (near-misses match or beat qualified) |
| Swing low intact | 3 | -0.209 | 0.182 | -0.391 | insufficient n |
| Uptrend (SMA50 > SMA200) | 26 | 0.429 | 0.182 | 0.247 | insufficient n |
| Volume contraction | 2692 | 0.152 | 0.182 | -0.030 | no measurable value in this sample |
| Weekly above 30-MA | 2 | -1.000 | 0.182 | -1.182 | insufficient n |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.2% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 4.2% of simulated entries were skipped due to the opening price being outside the stop/target range.
