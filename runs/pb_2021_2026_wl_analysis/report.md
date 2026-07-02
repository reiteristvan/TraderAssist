# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2021-01-01 → 2026-07-01
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 4f4fe68

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 3813 |
| Win rate | 34.1% |
| Avg win (R) | 1.98 |
| Avg loss (R) | -0.95 |
| Expectancy (R) | 0.050 |
| Median hold (days) | 5 |
| Max drawdown (R) | 330.80 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 2 | 50.0% | 0.186 | insufficient n |
| 70–84 | 98 | 36.7% | -0.093 | ok |
| 85–100 | 3690 | 34.0% | 0.056 | ok |

*Score bucket verdict: monotonically increasing*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 229 | 35.8% | -0.051 | ok |
| MEDIUM | 2639 | 34.7% | 0.062 | ok |
| HIGH | 945 | 31.7% | 0.043 | ok |

*Confidence bucket verdict: non-monotonic*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
| 2021-01 | 66 |
| 2021-02 | 58 |
| 2021-03 | 39 |
| 2021-04 | 143 |
| 2021-05 | 105 |
| 2021-06 | 36 |
| 2021-07 | 68 |
| 2021-08 | 77 |
| 2021-09 | 35 |
| 2021-10 | 49 |
| 2021-11 | 110 |
| 2021-12 | 21 |
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
| 2023-03 | 38 |
| 2023-04 | 48 |
| 2023-05 | 27 |
| 2023-06 | 2 |
| 2023-07 | 74 |
| 2023-08 | 79 |
| 2023-09 | 6 |
| 2023-10 | 3 |
| 2023-11 | 14 |
| 2023-12 | 12 |
| 2024-01 | 271 |
| 2024-02 | 43 |
| 2024-03 | 80 |
| 2024-04 | 146 |
| 2024-05 | 54 |
| 2024-06 | 83 |
| 2024-07 | 31 |
| 2024-08 | 329 |
| 2024-09 | 132 |
| 2024-10 | 199 |
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
| 2025-12 | 36 |
| 2026-01 | 90 |
| 2026-02 | 30 |
| 2026-03 | 34 |
| 2026-04 | 26 |
| 2026-05 | 137 |
| 2026-06 | 32 |


## Exit Reason Breakdown

| Reason | Count |
|--------|-------|
| stop | 2311 |
| target | 772 |
| time_stop | 730 |
| gap_skip_down | 159 |
| gap_skip_up | 17 |


## Non-winner Analysis

| Failure mode | Count | % |
|--------------|-------|---|
| Stop-out | 2311 | 92% |
| Time-stop | 203 | 8% |

*Stop-out dominated (92%) — setups are breaking down; the issue is setup quality rather than target distance.*


## Stop-out Forensics

| Metric | Value |
|--------|-------|
| Stop-outs | 2311 |
| % reached target post-stop | 11% |
| Median post-stop MFE | +0.23R |
| Winners' MAE near −1R (≤ −0.75) | 17% |

**Branch B** — 11% of stopped trades subsequently reached target (post-stop MFE median +0.23R) — stopped trades continued lower, consistent with genuine breakdown (Branch B: setups may lack edge at the current stop level → evaluate entry quality via E14.3/E14.4).


## Target Distance Analysis — by R-multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| 1.0–1.5×R | 502 | 34% | 0.039 |
| 1.5–2.0×R | 476 | 21% | -0.106 |
| 2.0–2.5×R | 452 | 18% | -0.087 |
| 2.5–3.0×R | 368 | 16% | -0.000 |
| 3.0+×R | 1659 | 10% | 0.160 |


## Target Distance Analysis — by ATR multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| <1.0 ATR | 172 | 71% | 0.060 |
| 1.0–1.5 ATR | 152 | 43% | -0.090 |
| 1.5–2.0 ATR | 727 | 32% | 0.016 |
| 2.0–2.5 ATR | 979 | 22% | 0.152 |
| 2.5+ ATR | 1783 | 8% | 0.020 |


## Winner/Loser Characteristic Analysis (Pre-registered)


### Pullback (winners: 1299, losers: 2514)

| Metric | Winners | Losers | Delta |
|--------|---------|--------|-------|
| RSI at entry | 52.6 | 50.8 | +1.8 |
| RVOL | 0.66x | 0.69x | -0.03 |
| Pullback depth % | +6.5% | +6.4% | +0.1% |
| ATR multiple | 2.22 | 2.57 | -0.35 |
| Industry momentum | +1.7% | +2.1% | -0.4% |
| Pct to 52w high | 6.7% | 6.7% | +0.0% |



## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |
|------|---------------|----------------|----------------|------|----------------|---------|
| 200-MA distance in range | 1302 | -0.060 | 0.050 | -0.110 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| At a logical support level | 1011 | -0.059 | 0.050 | -0.109 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Debt/equity acceptable | 664 | -0.051 | 0.050 | -0.102 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Earnings clear | 316 | 0.122 | 0.050 | 0.072 | **CUT** | no measurable value in this sample |
| Liquidity | 463 | -0.042 | 0.050 | -0.093 | **CUT** | no measurable value in this sample |
| Market cap in range | 1040 | -0.078 | 0.050 | -0.129 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Near 52w high in last 60d | 1403 | 0.013 | 0.050 | -0.037 | **CUT** | no measurable value in this sample |
| Profitable | 88 | 1.031 | 0.050 | 0.980 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback depth | 1532 | -0.053 | 0.050 | -0.104 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 1d | 93 | -0.286 | 0.050 | -0.337 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 21d | 159 | 0.310 | 0.050 | 0.260 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 22d | 137 | 0.027 | 0.050 | -0.024 | **CUT** | no measurable value in this sample |
| Pullback duration 23d | 132 | -0.109 | 0.050 | -0.160 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 24d | 118 | -0.225 | 0.050 | -0.275 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 25d | 113 | -0.035 | 0.050 | -0.086 | **CUT** | no measurable value in this sample |
| Pullback duration 26d | 115 | 0.333 | 0.050 | 0.282 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 27d | 111 | -0.010 | 0.050 | -0.061 | **CUT** | no measurable value in this sample |
| Pullback duration 28d | 111 | -0.072 | 0.050 | -0.123 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 29d | 118 | 0.157 | 0.050 | 0.106 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 2d | 186 | -0.039 | 0.050 | -0.089 | **CUT** | no measurable value in this sample |
| Pullback duration 30d | 124 | 0.234 | 0.050 | 0.184 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 31d | 121 | -0.016 | 0.050 | -0.066 | **CUT** | no measurable value in this sample |
| Pullback duration 32d | 121 | -0.004 | 0.050 | -0.054 | **CUT** | no measurable value in this sample |
| Pullback duration 33d | 113 | 0.273 | 0.050 | 0.223 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 34d | 109 | 0.073 | 0.050 | 0.023 | **CUT** | no measurable value in this sample |
| Pullback duration 35d | 109 | 0.263 | 0.050 | 0.212 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 36d | 120 | -0.176 | 0.050 | -0.227 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 37d | 128 | -0.183 | 0.050 | -0.233 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 38d | 127 | -0.080 | 0.050 | -0.130 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 39d | 219 | -0.186 | 0.050 | -0.237 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| RSI(14) reset | 186 | -0.068 | 0.050 | -0.118 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Relative strength vs SPY | 43 | 0.381 | 0.050 | 0.331 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| SMA50 rising (20 sessions) | 260 | -0.345 | 0.050 | -0.395 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLB) above 50MA | 65 | 0.140 | 0.050 | 0.089 | **CUT** | no measurable value in this sample |
| Sector (XLC) above 50MA | 19 | 0.746 | 0.050 | 0.696 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLE) above 50MA | 124 | -0.148 | 0.050 | -0.199 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLF) above 50MA | 221 | -0.529 | 0.050 | -0.580 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLI) above 50MA | 137 | -0.190 | 0.050 | -0.241 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLK) above 50MA | 127 | -0.065 | 0.050 | -0.116 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLP) above 50MA | 126 | 0.217 | 0.050 | 0.167 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Sector (XLRE) above 50MA | 87 | -0.002 | 0.050 | -0.052 | **CUT** | no measurable value in this sample |
| Sector (XLU) above 50MA | 29 | -0.618 | 0.050 | -0.669 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLV) above 50MA | 163 | 0.080 | 0.050 | 0.029 | **CUT** | no measurable value in this sample |
| Sector (XLY) above 50MA | 213 | 0.111 | 0.050 | 0.060 | **CUT** | no measurable value in this sample |
| Swing low intact | 61 | 0.232 | 0.050 | 0.181 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Uptrend (SMA50 > SMA200) | 37 | 0.302 | 0.050 | 0.251 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Volume contraction | 6998 | 0.027 | 0.050 | -0.024 | **CUT** | no measurable value in this sample |
| Weekly above 30-MA | 8 | -0.189 | 0.050 | -0.239 | **INSUFFICIENT-N** | insufficient n |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.4% of signals failed the earnings-proximity gate (earnings within 7 days of entry).

**Gap-skip rate** — 4.4% of simulated entries were skipped due to the opening price being outside the stop/target range.
