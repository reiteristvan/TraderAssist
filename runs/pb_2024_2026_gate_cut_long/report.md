# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2024-01-01 → 2026-06-25
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 6349b67

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 6506 |
| Win rate | 38.6% |
| Avg win (R) | 1.86 |
| Avg loss (R) | -0.94 |
| Expectancy (R) | 0.140 |
| Median hold (days) | 5 |
| Max drawdown (R) | 797.92 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 165 | 41.8% | 0.288 | ok |
| 55–69 | 449 | 36.1% | -0.048 | ok |
| 70–84 | 1034 | 41.1% | 0.094 | ok |
| 85–100 | 4566 | 38.0% | 0.174 | ok |

*Score bucket verdict: non-monotonic*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 613 | 40.8% | 0.040 | ok |
| MEDIUM | 4466 | 39.7% | 0.172 | ok |
| HIGH | 1427 | 34.1% | 0.082 | ok |

*Confidence bucket verdict: non-monotonic*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
| 2024-01 | 517 |
| 2024-02 | 256 |
| 2024-03 | 381 |
| 2024-04 | 245 |
| 2024-05 | 129 |
| 2024-06 | 213 |
| 2024-07 | 118 |
| 2024-08 | 713 |
| 2024-09 | 369 |
| 2024-10 | 525 |
| 2024-11 | 336 |
| 2024-12 | 611 |
| 2025-01 | 58 |
| 2025-02 | 140 |
| 2025-03 | 23 |
| 2025-04 | 4 |
| 2025-05 | 29 |
| 2025-06 | 64 |
| 2025-07 | 159 |
| 2025-08 | 174 |
| 2025-09 | 266 |
| 2025-10 | 169 |
| 2025-11 | 53 |
| 2025-12 | 211 |
| 2026-01 | 221 |
| 2026-02 | 138 |
| 2026-03 | 155 |
| 2026-04 | 81 |
| 2026-05 | 349 |
| 2026-06 | 119 |


## Exit Reason Breakdown

| Reason | Count |
|--------|-------|
| stop | 3636 |
| target | 1479 |
| time_stop | 1391 |
| gap_skip_down | 278 |
| gap_skip_up | 40 |
| incomplete | 2 |


## Non-winner Analysis

| Failure mode | Count | % |
|--------------|-------|---|
| Stop-out | 3636 | 91% |
| Time-stop | 358 | 9% |

*Stop-out dominated (91%) — setups are breaking down; the issue is setup quality rather than target distance.*


## Stop-out Forensics

| Metric | Value |
|--------|-------|
| Stop-outs | 3636 |
| % reached target post-stop | 11% |
| Median post-stop MFE | +0.39R |
| Winners' MAE near −1R (≤ −0.75) | 16% |

**Branch B** — 11% of stopped trades subsequently reached target (post-stop MFE median +0.39R) — stopped trades continued lower, consistent with genuine breakdown (Branch B: setups may lack edge at the current stop level → evaluate entry quality via E14.3/E14.4).


## Target Distance Analysis — by R-multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| 1.0–1.5×R | 838 | 36% | 0.106 |
| 1.5–2.0×R | 802 | 26% | 0.080 |
| 2.0–2.5×R | 732 | 19% | 0.044 |
| 2.5–3.0×R | 634 | 17% | 0.088 |
| 3.0+×R | 2770 | 10% | 0.227 |


## Target Distance Analysis — by ATR multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| <1.0 ATR | 408 | 73% | 0.034 |
| 1.0–1.5 ATR | 257 | 47% | -0.034 |
| 1.5–2.0 ATR | 1251 | 34% | 0.070 |
| 2.0–2.5 ATR | 1509 | 24% | 0.233 |
| 2.5+ ATR | 3081 | 9% | 0.151 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |
|------|---------------|----------------|----------------|------|----------------|---------|
| 200-MA distance in range | 1319 | -0.065 | 0.140 | -0.204 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| At a logical support level | 1431 | 0.114 | 0.140 | -0.026 | **CUT** | no measurable value in this sample |
| Debt/equity acceptable | 1074 | -0.022 | 0.140 | -0.162 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Earnings clear | 377 | 0.346 | 0.140 | 0.206 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Liquidity | 510 | 0.072 | 0.140 | -0.068 | **CUT** | no measurable value in this sample |
| Market cap in range | 1747 | -0.006 | 0.140 | -0.145 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Near 52w high in last 60d | 2007 | -0.014 | 0.140 | -0.154 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Profitable | 126 | 0.600 | 0.140 | 0.460 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback depth | 2020 | 0.083 | 0.140 | -0.057 | **CUT** | no measurable value in this sample |
| Pullback duration 1d | 218 | 0.120 | 0.140 | -0.020 | **CUT** | no measurable value in this sample |
| Pullback duration 21d | 237 | 0.210 | 0.140 | 0.070 | **CUT** | no measurable value in this sample |
| Pullback duration 22d | 201 | 0.188 | 0.140 | 0.048 | **CUT** | no measurable value in this sample |
| Pullback duration 23d | 200 | -0.028 | 0.140 | -0.168 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 24d | 189 | -0.242 | 0.140 | -0.381 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 25d | 174 | -0.075 | 0.140 | -0.215 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 26d | 157 | 0.078 | 0.140 | -0.062 | **CUT** | no measurable value in this sample |
| Pullback duration 27d | 157 | -0.212 | 0.140 | -0.352 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 28d | 148 | 0.003 | 0.140 | -0.137 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 29d | 170 | 0.320 | 0.140 | 0.181 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 2d | 373 | 0.041 | 0.140 | -0.099 | **CUT** | no measurable value in this sample |
| Pullback duration 30d | 178 | 0.432 | 0.140 | 0.293 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 31d | 175 | 0.020 | 0.140 | -0.120 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 32d | 164 | 0.024 | 0.140 | -0.116 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 33d | 164 | 0.394 | 0.140 | 0.255 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 34d | 170 | -0.010 | 0.140 | -0.150 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 35d | 172 | 0.332 | 0.140 | 0.192 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 36d | 177 | -0.031 | 0.140 | -0.170 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 37d | 199 | -0.029 | 0.140 | -0.168 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 38d | 216 | -0.243 | 0.140 | -0.383 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 39d | 335 | -0.298 | 0.140 | -0.438 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| RSI(14) reset | 428 | -0.020 | 0.140 | -0.160 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Relative strength vs SPY | 71 | 0.738 | 0.140 | 0.598 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| SMA50 rising (20 sessions) | 316 | -0.208 | 0.140 | -0.348 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLB) above 50MA | 137 | -0.277 | 0.140 | -0.417 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLC) above 50MA | 44 | 0.199 | 0.140 | 0.059 | **CUT** | no measurable value in this sample |
| Sector (XLE) above 50MA | 162 | -0.046 | 0.140 | -0.186 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLF) above 50MA | 594 | -0.232 | 0.140 | -0.371 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLI) above 50MA | 211 | -0.027 | 0.140 | -0.166 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLK) above 50MA | 238 | 0.149 | 0.140 | 0.009 | **CUT** | no measurable value in this sample |
| Sector (XLP) above 50MA | 133 | 0.096 | 0.140 | -0.044 | **CUT** | no measurable value in this sample |
| Sector (XLRE) above 50MA | 195 | 0.202 | 0.140 | 0.062 | **CUT** | no measurable value in this sample |
| Sector (XLU) above 50MA | 52 | -0.010 | 0.140 | -0.149 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLV) above 50MA | 267 | 0.269 | 0.140 | 0.129 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Sector (XLY) above 50MA | 285 | 0.157 | 0.140 | 0.018 | **CUT** | no measurable value in this sample |
| Swing low intact | 245 | -0.001 | 0.140 | -0.140 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Uptrend (SMA50 > SMA200) | 72 | 0.151 | 0.140 | 0.012 | **CUT** | no measurable value in this sample |
| Weekly above 30-MA | 31 | -0.484 | 0.140 | -0.623 | **KEEP** | near-misses underperform qualified (gate shows protective value) |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.6% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 4.7% of simulated entries were skipped due to the opening price being outside the stop/target range.
