# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2024-01-01 → 2026-06-25
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 4247d20

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 1903 |
| Win rate | 36.7% |
| Avg win (R) | 1.88 |
| Avg loss (R) | -0.93 |
| Expectancy (R) | 0.100 |
| Median hold (days) | 6 |
| Max drawdown (R) | 300.12 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 2 | 50.0% | 0.186 | insufficient n |
| 70–84 | 57 | 45.6% | 0.006 | ok |
| 85–100 | 1828 | 36.4% | 0.106 | ok |

*Score bucket verdict: monotonically increasing*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 72 | 37.5% | 0.016 | ok |
| MEDIUM | 1308 | 38.8% | 0.133 | ok |
| HIGH | 523 | 31.5% | 0.030 | ok |

*Confidence bucket verdict: non-monotonic*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
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
| stop | 1072 |
| cooldown_skip | 533 |
| time_stop | 417 |
| target | 414 |
| gap_skip_down | 53 |
| gap_skip_up | 9 |


## Non-winner Analysis

| Failure mode | Count | % |
|--------------|-------|---|
| Stop-out | 1072 | 89% |
| Time-stop | 132 | 11% |

*Stop-out dominated (89%) — setups are breaking down; the issue is setup quality rather than target distance.*


## Stop-out Forensics

| Metric | Value |
|--------|-------|
| Stop-outs | 1072 |
| % reached target post-stop | 11% |
| Median post-stop MFE | +0.05R |
| Winners' MAE near −1R (≤ −0.75) | 18% |

**Branch B** — 11% of stopped trades subsequently reached target (post-stop MFE median +0.05R) — stopped trades continued lower, consistent with genuine breakdown (Branch B: setups may lack edge at the current stop level → evaluate entry quality via E14.3/E14.4).


## Target Distance Analysis — by R-multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| 1.0–1.5×R | 287 | 35% | 0.069 |
| 1.5–2.0×R | 264 | 20% | -0.128 |
| 2.0–2.5×R | 235 | 17% | -0.123 |
| 2.5–3.0×R | 196 | 15% | 0.038 |
| 3.0+×R | 719 | 10% | 0.303 |


## Target Distance Analysis — by ATR multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| <1.0 ATR | 90 | 74% | 0.070 |
| 1.0–1.5 ATR | 80 | 44% | -0.090 |
| 1.5–2.0 ATR | 371 | 34% | -0.004 |
| 2.0–2.5 ATR | 454 | 25% | 0.193 |
| 2.5+ ATR | 908 | 8% | 0.116 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |
|------|---------------|----------------|----------------|------|----------------|---------|
| 200-MA distance in range | 476 | -0.080 | 0.100 | -0.180 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| At a logical support level | 647 | -0.024 | 0.100 | -0.125 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Debt/equity acceptable | 370 | -0.095 | 0.100 | -0.195 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Earnings clear | 175 | 0.115 | 0.100 | 0.014 | **CUT** | no measurable value in this sample |
| Liquidity | 165 | 0.221 | 0.100 | 0.120 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Market cap in range | 622 | -0.015 | 0.100 | -0.115 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Near 52w high in last 60d | 790 | 0.047 | 0.100 | -0.053 | **CUT** | no measurable value in this sample |
| Profitable | 54 | 1.288 | 0.100 | 1.188 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback depth | 816 | 0.105 | 0.100 | 0.005 | **CUT** | no measurable value in this sample |
| Pullback duration 1d | 49 | -0.146 | 0.100 | -0.247 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 21d | 96 | 0.547 | 0.100 | 0.447 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 22d | 82 | 0.082 | 0.100 | -0.019 | **CUT** | no measurable value in this sample |
| Pullback duration 23d | 82 | -0.036 | 0.100 | -0.136 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 24d | 78 | -0.294 | 0.100 | -0.394 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 25d | 66 | 0.028 | 0.100 | -0.072 | **CUT** | no measurable value in this sample |
| Pullback duration 26d | 68 | 0.380 | 0.100 | 0.280 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 27d | 70 | -0.128 | 0.100 | -0.229 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 28d | 70 | -0.164 | 0.100 | -0.264 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 29d | 78 | 0.254 | 0.100 | 0.154 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 2d | 108 | 0.028 | 0.100 | -0.072 | **CUT** | no measurable value in this sample |
| Pullback duration 30d | 82 | 0.348 | 0.100 | 0.247 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 31d | 81 | 0.059 | 0.100 | -0.042 | **CUT** | no measurable value in this sample |
| Pullback duration 32d | 83 | 0.031 | 0.100 | -0.069 | **CUT** | no measurable value in this sample |
| Pullback duration 33d | 80 | 0.369 | 0.100 | 0.268 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 34d | 73 | 0.073 | 0.100 | -0.027 | **CUT** | no measurable value in this sample |
| Pullback duration 35d | 70 | 0.502 | 0.100 | 0.401 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 36d | 75 | -0.185 | 0.100 | -0.285 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 37d | 81 | 0.025 | 0.100 | -0.075 | **CUT** | no measurable value in this sample |
| Pullback duration 38d | 88 | -0.180 | 0.100 | -0.281 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 39d | 144 | -0.176 | 0.100 | -0.276 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| RSI(14) reset | 138 | -0.069 | 0.100 | -0.169 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Relative strength vs SPY | 23 | 0.723 | 0.100 | 0.623 | **INSUFFICIENT-N** | insufficient n |
| SMA50 rising (20 sessions) | 135 | -0.506 | 0.100 | -0.606 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLB) above 50MA | 55 | 0.144 | 0.100 | 0.044 | **CUT** | no measurable value in this sample |
| Sector (XLC) above 50MA | 16 | 0.118 | 0.100 | 0.018 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLE) above 50MA | 76 | -0.011 | 0.100 | -0.112 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLF) above 50MA | 131 | -0.641 | 0.100 | -0.741 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLI) above 50MA | 85 | -0.113 | 0.100 | -0.213 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLK) above 50MA | 72 | 0.000 | 0.100 | -0.100 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLP) above 50MA | 62 | -0.074 | 0.100 | -0.175 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLRE) above 50MA | 71 | -0.061 | 0.100 | -0.161 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLU) above 50MA | 9 | -0.290 | 0.100 | -0.390 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLV) above 50MA | 85 | 0.181 | 0.100 | 0.081 | **CUT** | no measurable value in this sample |
| Sector (XLY) above 50MA | 100 | 0.065 | 0.100 | -0.036 | **CUT** | no measurable value in this sample |
| Swing low intact | 42 | 0.197 | 0.100 | 0.096 | **CUT** | no measurable value in this sample |
| Uptrend (SMA50 > SMA200) | 31 | 0.453 | 0.100 | 0.353 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Volume contraction | 4124 | 0.123 | 0.100 | 0.023 | **CUT** | no measurable value in this sample |
| Weekly above 30-MA | 4 | -1.000 | 0.100 | -1.100 | **INSUFFICIENT-N** | insufficient n |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.4% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 2.5% of simulated entries were skipped due to the opening price being outside the stop/target range.
