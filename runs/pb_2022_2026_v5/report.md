# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2022-01-01 → 2026-06-25
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 2226f1f

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 3043 |
| Win rate | 34.3% |
| Avg win (R) | 2.04 |
| Avg loss (R) | -0.95 |
| Expectancy (R) | 0.080 |
| Median hold (days) | 5 |
| Max drawdown (R) | 330.80 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 2 | 50.0% | 0.186 | insufficient n |
| 70–84 | 74 | 40.5% | -0.037 | ok |
| 85–100 | 2948 | 34.2% | 0.084 | ok |

*Score bucket verdict: monotonically increasing*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 180 | 35.6% | -0.057 | ok |
| MEDIUM | 2081 | 35.8% | 0.117 | ok |
| HIGH | 782 | 30.3% | 0.014 | ok |

*Confidence bucket verdict: non-monotonic*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
| 2022-01 | 32 |
| 2022-02 | 16 |
| 2022-03 | 2 |
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
| stop | 1829 |
| target | 636 |
| time_stop | 578 |
| gap_skip_down | 129 |
| gap_skip_up | 17 |


## Non-winner Analysis

| Failure mode | Count | % |
|--------------|-------|---|
| Stop-out | 1829 | 92% |
| Time-stop | 169 | 8% |

*Stop-out dominated (92%) — setups are breaking down; the issue is setup quality rather than target distance.*


## Stop-out Forensics

| Metric | Value |
|--------|-------|
| Stop-outs | 1829 |
| % reached target post-stop | 12% |
| Median post-stop MFE | +0.22R |
| Winners' MAE near −1R (≤ −0.75) | 18% |

**Branch B** — 12% of stopped trades subsequently reached target (post-stop MFE median +0.22R) — stopped trades continued lower, consistent with genuine breakdown (Branch B: setups may lack edge at the current stop level → evaluate entry quality via E14.3/E14.4).


## Target Distance Analysis — by R-multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| 1.0–1.5×R | 391 | 37% | 0.088 |
| 1.5–2.0×R | 386 | 22% | -0.067 |
| 2.0–2.5×R | 355 | 18% | -0.081 |
| 2.5–3.0×R | 289 | 17% | 0.041 |
| 3.0+×R | 1333 | 10% | 0.187 |


## Target Distance Analysis — by ATR multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| <1.0 ATR | 137 | 72% | 0.070 |
| 1.0–1.5 ATR | 123 | 43% | -0.089 |
| 1.5–2.0 ATR | 564 | 34% | 0.050 |
| 2.0–2.5 ATR | 767 | 23% | 0.216 |
| 2.5+ ATR | 1452 | 8% | 0.035 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |
|------|---------------|----------------|----------------|------|----------------|---------|
| 200-MA distance in range | 658 | -0.149 | 0.080 | -0.228 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| At a logical support level | 842 | -0.031 | 0.080 | -0.111 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Debt/equity acceptable | 507 | -0.096 | 0.080 | -0.175 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Earnings clear | 243 | 0.082 | 0.080 | 0.003 | **CUT** | no measurable value in this sample |
| Liquidity | 275 | 0.034 | 0.080 | -0.046 | **CUT** | no measurable value in this sample |
| Market cap in range | 808 | -0.040 | 0.080 | -0.120 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Near 52w high in last 60d | 1188 | -0.031 | 0.080 | -0.111 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Profitable | 67 | 1.235 | 0.080 | 1.155 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback depth | 1050 | 0.026 | 0.080 | -0.054 | **CUT** | no measurable value in this sample |
| Pullback duration 1d | 66 | -0.218 | 0.080 | -0.298 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 21d | 122 | 0.373 | 0.080 | 0.294 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 22d | 101 | 0.124 | 0.080 | 0.044 | **CUT** | no measurable value in this sample |
| Pullback duration 23d | 103 | -0.098 | 0.080 | -0.178 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 24d | 90 | -0.190 | 0.080 | -0.270 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 25d | 82 | 0.001 | 0.080 | -0.078 | **CUT** | no measurable value in this sample |
| Pullback duration 26d | 90 | 0.202 | 0.080 | 0.122 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 27d | 88 | -0.112 | 0.080 | -0.191 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 28d | 86 | -0.136 | 0.080 | -0.216 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 29d | 97 | 0.270 | 0.080 | 0.190 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 2d | 136 | 0.006 | 0.080 | -0.074 | **CUT** | no measurable value in this sample |
| Pullback duration 30d | 99 | 0.272 | 0.080 | 0.192 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 31d | 99 | -0.018 | 0.080 | -0.098 | **CUT** | no measurable value in this sample |
| Pullback duration 32d | 100 | -0.037 | 0.080 | -0.117 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 33d | 94 | 0.342 | 0.080 | 0.262 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 34d | 92 | 0.065 | 0.080 | -0.015 | **CUT** | no measurable value in this sample |
| Pullback duration 35d | 89 | 0.259 | 0.080 | 0.179 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 36d | 94 | -0.209 | 0.080 | -0.289 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 37d | 105 | -0.102 | 0.080 | -0.182 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 38d | 103 | -0.235 | 0.080 | -0.315 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 39d | 172 | -0.211 | 0.080 | -0.291 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| RSI(14) reset | 169 | -0.071 | 0.080 | -0.151 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Relative strength vs SPY | 28 | 0.553 | 0.080 | 0.473 | **INSUFFICIENT-N** | insufficient n |
| SMA50 rising (20 sessions) | 192 | -0.469 | 0.080 | -0.549 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLB) above 50MA | 61 | 0.080 | 0.080 | 0.000 | **CUT** | no measurable value in this sample |
| Sector (XLC) above 50MA | 19 | 0.746 | 0.080 | 0.666 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLE) above 50MA | 124 | -0.148 | 0.080 | -0.228 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLF) above 50MA | 190 | -0.529 | 0.080 | -0.609 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLI) above 50MA | 124 | -0.133 | 0.080 | -0.212 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLK) above 50MA | 102 | -0.132 | 0.080 | -0.212 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLP) above 50MA | 110 | 0.210 | 0.080 | 0.131 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Sector (XLRE) above 50MA | 87 | -0.008 | 0.080 | -0.088 | **CUT** | no measurable value in this sample |
| Sector (XLU) above 50MA | 17 | -0.624 | 0.080 | -0.704 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLV) above 50MA | 141 | 0.126 | 0.080 | 0.047 | **CUT** | no measurable value in this sample |
| Sector (XLY) above 50MA | 164 | 0.199 | 0.080 | 0.119 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Swing low intact | 43 | 0.169 | 0.080 | 0.089 | **CUT** | no measurable value in this sample |
| Uptrend (SMA50 > SMA200) | 37 | 0.302 | 0.080 | 0.222 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Volume contraction | 5576 | 0.042 | 0.080 | -0.038 | **CUT** | no measurable value in this sample |
| Weekly above 30-MA | 7 | -0.073 | 0.080 | -0.153 | **INSUFFICIENT-N** | insufficient n |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.4% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 4.6% of simulated entries were skipped due to the opening price being outside the stop/target range.
