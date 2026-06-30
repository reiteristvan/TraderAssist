# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2022-01-01 → 2026-06-25
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 4247d20

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 3010 |
| Win rate | 34.3% |
| Avg win (R) | 2.05 |
| Avg loss (R) | -0.95 |
| Expectancy (R) | 0.082 |
| Median hold (days) | 5 |
| Max drawdown (R) | 330.80 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 2 | 50.0% | 0.186 | insufficient n |
| 70–84 | 74 | 40.5% | -0.035 | ok |
| 85–100 | 2916 | 34.1% | 0.087 | ok |

*Score bucket verdict: monotonically increasing*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 179 | 34.6% | -0.088 | ok |
| MEDIUM | 2071 | 35.6% | 0.116 | ok |
| HIGH | 760 | 30.5% | 0.032 | ok |

*Confidence bucket verdict: non-monotonic*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
| 2022-01 | 32 |
| 2022-02 | 16 |
| 2022-03 | 2 |
| 2022-04 | 27 |
| 2022-05 | 10 |
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
| 2023-05 | 30 |
| 2023-06 | 3 |
| 2023-07 | 76 |
| 2023-08 | 82 |
| 2023-09 | 6 |
| 2023-10 | 3 |
| 2023-11 | 14 |
| 2023-12 | 12 |
| 2024-01 | 274 |
| 2024-02 | 51 |
| 2024-03 | 80 |
| 2024-04 | 146 |
| 2024-05 | 51 |
| 2024-06 | 80 |
| 2024-07 | 31 |
| 2024-08 | 325 |
| 2024-09 | 132 |
| 2024-10 | 200 |
| 2024-11 | 104 |
| 2024-12 | 316 |
| 2025-01 | 18 |
| 2025-02 | 45 |
| 2025-03 | 1 |
| 2025-04 | 3 |
| 2025-05 | 14 |
| 2025-06 | 24 |
| 2025-07 | 52 |
| 2025-08 | 37 |
| 2025-09 | 68 |
| 2025-10 | 58 |
| 2025-11 | 6 |
| 2025-12 | 37 |
| 2026-01 | 90 |
| 2026-02 | 30 |
| 2026-03 | 34 |
| 2026-04 | 21 |
| 2026-05 | 138 |
| 2026-06 | 32 |


## Exit Reason Breakdown

| Reason | Count |
|--------|-------|
| stop | 1810 |
| target | 625 |
| time_stop | 575 |
| gap_skip_down | 125 |
| gap_skip_up | 18 |


## Non-winner Analysis

| Failure mode | Count | % |
|--------------|-------|---|
| Stop-out | 1810 | 91% |
| Time-stop | 169 | 9% |

*Stop-out dominated (91%) — setups are breaking down; the issue is setup quality rather than target distance.*


## Stop-out Forensics

| Metric | Value |
|--------|-------|
| Stop-outs | 1810 |
| % reached target post-stop | 12% |
| Median post-stop MFE | +0.22R |
| Winners' MAE near −1R (≤ −0.75) | 18% |

**Branch B** — 12% of stopped trades subsequently reached target (post-stop MFE median +0.22R) — stopped trades continued lower, consistent with genuine breakdown (Branch B: setups may lack edge at the current stop level → evaluate entry quality via E14.3/E14.4).


## Target Distance Analysis — by R-multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| 1.0–1.5×R | 388 | 36% | 0.085 |
| 1.5–2.0×R | 379 | 22% | -0.078 |
| 2.0–2.5×R | 350 | 18% | -0.091 |
| 2.5–3.0×R | 287 | 17% | 0.051 |
| 3.0+×R | 1320 | 10% | 0.197 |


## Target Distance Analysis — by ATR multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| <1.0 ATR | 135 | 72% | 0.066 |
| 1.0–1.5 ATR | 123 | 43% | -0.089 |
| 1.5–2.0 ATR | 559 | 34% | 0.059 |
| 2.0–2.5 ATR | 758 | 23% | 0.213 |
| 2.5+ ATR | 1435 | 8% | 0.039 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |
|------|---------------|----------------|----------------|------|----------------|---------|
| 200-MA distance in range | 663 | -0.135 | 0.082 | -0.218 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| At a logical support level | 843 | -0.038 | 0.082 | -0.120 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Debt/equity acceptable | 520 | -0.126 | 0.082 | -0.209 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Earnings clear | 239 | 0.058 | 0.082 | -0.024 | **CUT** | no measurable value in this sample |
| Liquidity | 275 | 0.034 | 0.082 | -0.048 | **CUT** | no measurable value in this sample |
| Market cap in range | 839 | -0.047 | 0.082 | -0.129 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Near 52w high in last 60d | 1183 | -0.034 | 0.082 | -0.116 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Profitable | 67 | 0.844 | 0.082 | 0.762 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback depth | 1050 | 0.024 | 0.082 | -0.058 | **CUT** | no measurable value in this sample |
| Pullback duration 1d | 65 | -0.242 | 0.082 | -0.324 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 21d | 122 | 0.374 | 0.082 | 0.292 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 22d | 100 | 0.095 | 0.082 | 0.013 | **CUT** | no measurable value in this sample |
| Pullback duration 23d | 100 | -0.078 | 0.082 | -0.161 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 24d | 90 | -0.215 | 0.082 | -0.297 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 25d | 81 | -0.018 | 0.082 | -0.100 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 26d | 88 | 0.222 | 0.082 | 0.140 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 27d | 88 | -0.104 | 0.082 | -0.186 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 28d | 86 | -0.124 | 0.082 | -0.206 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 29d | 97 | 0.210 | 0.082 | 0.128 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 2d | 135 | 0.012 | 0.082 | -0.071 | **CUT** | no measurable value in this sample |
| Pullback duration 30d | 99 | 0.258 | 0.082 | 0.176 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 31d | 99 | -0.036 | 0.082 | -0.119 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 32d | 100 | -0.049 | 0.082 | -0.131 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 33d | 94 | 0.331 | 0.082 | 0.248 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 34d | 91 | 0.076 | 0.082 | -0.006 | **CUT** | no measurable value in this sample |
| Pullback duration 35d | 89 | 0.248 | 0.082 | 0.165 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 36d | 93 | -0.214 | 0.082 | -0.297 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 37d | 105 | -0.102 | 0.082 | -0.185 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 38d | 103 | -0.235 | 0.082 | -0.317 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 39d | 174 | -0.220 | 0.082 | -0.303 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| RSI(14) reset | 166 | -0.054 | 0.082 | -0.136 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Relative strength vs SPY | 28 | 0.555 | 0.082 | 0.473 | **INSUFFICIENT-N** | insufficient n |
| SMA50 rising (20 sessions) | 193 | -0.472 | 0.082 | -0.554 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLB) above 50MA | 61 | 0.080 | 0.082 | -0.002 | **CUT** | no measurable value in this sample |
| Sector (XLC) above 50MA | 18 | -0.006 | 0.082 | -0.088 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLE) above 50MA | 116 | -0.137 | 0.082 | -0.219 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLF) above 50MA | 192 | -0.548 | 0.082 | -0.631 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLI) above 50MA | 124 | -0.133 | 0.082 | -0.215 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLK) above 50MA | 102 | -0.132 | 0.082 | -0.215 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLP) above 50MA | 110 | 0.210 | 0.082 | 0.128 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Sector (XLRE) above 50MA | 87 | -0.006 | 0.082 | -0.089 | **CUT** | no measurable value in this sample |
| Sector (XLU) above 50MA | 17 | -0.624 | 0.082 | -0.706 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLV) above 50MA | 141 | 0.126 | 0.082 | 0.044 | **CUT** | no measurable value in this sample |
| Sector (XLY) above 50MA | 152 | 0.185 | 0.082 | 0.103 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Swing low intact | 43 | 0.169 | 0.082 | 0.087 | **CUT** | no measurable value in this sample |
| Uptrend (SMA50 > SMA200) | 37 | 0.302 | 0.082 | 0.220 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Volume contraction | 5552 | 0.038 | 0.082 | -0.044 | **CUT** | no measurable value in this sample |
| Weekly above 30-MA | 5 | -0.561 | 0.082 | -0.644 | **INSUFFICIENT-N** | insufficient n |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.4% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 4.5% of simulated entries were skipped due to the opening price being outside the stop/target range.
