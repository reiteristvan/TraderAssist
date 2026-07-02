# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2022-04-01 → 2026-06-30
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: d5be283

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 2995 |
| Win rate | 34.4% |
| Avg win (R) | 2.05 |
| Avg loss (R) | -0.95 |
| Expectancy (R) | 0.088 |
| Median hold (days) | 5 |
| Max drawdown (R) | 330.80 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 2 | 50.0% | 0.186 | insufficient n |
| 70–84 | 74 | 40.5% | -0.037 | ok |
| 85–100 | 2901 | 34.2% | 0.092 | ok |

*Score bucket verdict: monotonically increasing*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 176 | 35.2% | -0.055 | ok |
| MEDIUM | 2045 | 35.8% | 0.124 | ok |
| HIGH | 774 | 30.6% | 0.024 | ok |

*Confidence bucket verdict: non-monotonic*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
| 2022-04 | 34 |
| 2022-05 | 12 |
| 2022-06 | 3 |
| 2022-07 | 3 |
| 2022-08 | 38 |
| 2022-09 | 17 |
| 2022-10 | 1 |
| 2022-11 | 61 |
| 2022-12 | 66 |
| 2023-01 | 15 |
| 2023-02 | 52 |
| 2023-03 | 33 |
| 2023-04 | 48 |
| 2023-05 | 30 |
| 2023-06 | 2 |
| 2023-07 | 72 |
| 2023-08 | 81 |
| 2023-09 | 6 |
| 2023-10 | 3 |
| 2023-11 | 14 |
| 2023-12 | 12 |
| 2024-01 | 274 |
| 2024-02 | 50 |
| 2024-03 | 80 |
| 2024-04 | 146 |
| 2024-05 | 54 |
| 2024-06 | 83 |
| 2024-07 | 31 |
| 2024-08 | 325 |
| 2024-09 | 132 |
| 2024-10 | 201 |
| 2024-11 | 104 |
| 2024-12 | 317 |
| 2025-01 | 18 |
| 2025-02 | 45 |
| 2025-03 | 1 |
| 2025-04 | 3 |
| 2025-05 | 14 |
| 2025-06 | 24 |
| 2025-07 | 52 |
| 2025-08 | 48 |
| 2025-09 | 82 |
| 2025-10 | 60 |
| 2025-11 | 6 |
| 2025-12 | 37 |
| 2026-01 | 90 |
| 2026-02 | 30 |
| 2026-03 | 34 |
| 2026-04 | 26 |
| 2026-05 | 137 |
| 2026-06 | 32 |


## Exit Reason Breakdown

| Reason | Count |
|--------|-------|
| stop | 1796 |
| target | 632 |
| time_stop | 567 |
| gap_skip_down | 127 |
| gap_skip_up | 17 |


## Non-winner Analysis

| Failure mode | Count | % |
|--------------|-------|---|
| Stop-out | 1796 | 91% |
| Time-stop | 168 | 9% |

*Stop-out dominated (91%) — setups are breaking down; the issue is setup quality rather than target distance.*


## Stop-out Forensics

| Metric | Value |
|--------|-------|
| Stop-outs | 1796 |
| % reached target post-stop | 12% |
| Median post-stop MFE | +0.23R |
| Winners' MAE near −1R (≤ −0.75) | 18% |

**Branch B** — 12% of stopped trades subsequently reached target (post-stop MFE median +0.23R) — stopped trades continued lower, consistent with genuine breakdown (Branch B: setups may lack edge at the current stop level → evaluate entry quality via E14.3/E14.4).


## Target Distance Analysis — by R-multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| 1.0–1.5×R | 390 | 37% | 0.091 |
| 1.5–2.0×R | 381 | 22% | -0.068 |
| 2.0–2.5×R | 345 | 19% | -0.069 |
| 2.5–3.0×R | 284 | 17% | 0.033 |
| 3.0+×R | 1311 | 10% | 0.201 |


## Target Distance Analysis — by ATR multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| <1.0 ATR | 134 | 73% | 0.079 |
| 1.0–1.5 ATR | 120 | 43% | -0.081 |
| 1.5–2.0 ATR | 561 | 34% | 0.043 |
| 2.0–2.5 ATR | 752 | 24% | 0.227 |
| 2.5+ ATR | 1428 | 8% | 0.046 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |
|------|---------------|----------------|----------------|------|----------------|---------|
| 200-MA distance in range | 648 | -0.135 | 0.088 | -0.223 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| At a logical support level | 838 | -0.029 | 0.088 | -0.117 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Debt/equity acceptable | 493 | -0.073 | 0.088 | -0.160 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Earnings clear | 243 | 0.082 | 0.088 | -0.005 | **CUT** | no measurable value in this sample |
| Liquidity | 249 | -0.014 | 0.088 | -0.101 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Market cap in range | 800 | -0.030 | 0.088 | -0.117 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Near 52w high in last 60d | 1179 | -0.034 | 0.088 | -0.122 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Profitable | 63 | 1.377 | 0.088 | 1.289 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback depth | 1032 | 0.044 | 0.088 | -0.044 | **CUT** | no measurable value in this sample |
| Pullback duration 1d | 63 | -0.218 | 0.088 | -0.305 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 21d | 120 | 0.389 | 0.088 | 0.301 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 22d | 100 | 0.129 | 0.088 | 0.041 | **CUT** | no measurable value in this sample |
| Pullback duration 23d | 102 | -0.089 | 0.088 | -0.177 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 24d | 89 | -0.181 | 0.088 | -0.268 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 25d | 81 | 0.014 | 0.088 | -0.074 | **CUT** | no measurable value in this sample |
| Pullback duration 26d | 89 | 0.216 | 0.088 | 0.128 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 27d | 87 | -0.116 | 0.088 | -0.204 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 28d | 85 | -0.146 | 0.088 | -0.234 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 29d | 95 | 0.277 | 0.088 | 0.189 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 2d | 131 | 0.011 | 0.088 | -0.077 | **CUT** | no measurable value in this sample |
| Pullback duration 30d | 97 | 0.298 | 0.088 | 0.211 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 31d | 96 | 0.006 | 0.088 | -0.082 | **CUT** | no measurable value in this sample |
| Pullback duration 32d | 99 | -0.027 | 0.088 | -0.115 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 33d | 94 | 0.342 | 0.088 | 0.254 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 34d | 91 | 0.076 | 0.088 | -0.011 | **CUT** | no measurable value in this sample |
| Pullback duration 35d | 88 | 0.273 | 0.088 | 0.186 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 36d | 92 | -0.213 | 0.088 | -0.301 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 37d | 102 | -0.098 | 0.088 | -0.185 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 38d | 101 | -0.220 | 0.088 | -0.307 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 39d | 168 | -0.200 | 0.088 | -0.288 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| RSI(14) reset | 169 | -0.071 | 0.088 | -0.158 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Relative strength vs SPY | 28 | 0.553 | 0.088 | 0.465 | **INSUFFICIENT-N** | insufficient n |
| SMA50 rising (20 sessions) | 180 | -0.469 | 0.088 | -0.557 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLB) above 50MA | 60 | 0.098 | 0.088 | 0.010 | **CUT** | no measurable value in this sample |
| Sector (XLC) above 50MA | 19 | 0.746 | 0.088 | 0.658 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLE) above 50MA | 124 | -0.148 | 0.088 | -0.236 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLF) above 50MA | 169 | -0.603 | 0.088 | -0.691 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLI) above 50MA | 122 | -0.118 | 0.088 | -0.206 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLK) above 50MA | 86 | -0.050 | 0.088 | -0.138 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLP) above 50MA | 106 | 0.185 | 0.088 | 0.098 | **CUT** | no measurable value in this sample |
| Sector (XLRE) above 50MA | 82 | -0.003 | 0.088 | -0.091 | **CUT** | no measurable value in this sample |
| Sector (XLU) above 50MA | 17 | -0.624 | 0.088 | -0.711 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLV) above 50MA | 135 | 0.154 | 0.088 | 0.066 | **CUT** | no measurable value in this sample |
| Sector (XLY) above 50MA | 160 | 0.229 | 0.088 | 0.142 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Swing low intact | 43 | 0.169 | 0.088 | 0.082 | **CUT** | no measurable value in this sample |
| Uptrend (SMA50 > SMA200) | 35 | 0.287 | 0.088 | 0.199 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Volume contraction | 5319 | 0.059 | 0.088 | -0.028 | **CUT** | no measurable value in this sample |
| Weekly above 30-MA | 7 | -0.073 | 0.088 | -0.161 | **INSUFFICIENT-N** | insufficient n |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.5% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 4.6% of simulated entries were skipped due to the opening price being outside the stop/target range.
