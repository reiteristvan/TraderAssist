# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2024-01-01 → 2026-06-30
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 4247d20

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 2416 |
| Win rate | 35.8% |
| Avg win (R) | 2.13 |
| Avg loss (R) | -0.94 |
| Expectancy (R) | 0.161 |
| Median hold (days) | 5 |
| Max drawdown (R) | 330.80 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 2 | 50.0% | 0.186 | insufficient n |
| 70–84 | 66 | 43.9% | -0.004 | ok |
| 85–100 | 2331 | 35.6% | 0.168 | ok |

*Score bucket verdict: monotonically increasing*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 98 | 37.8% | -0.028 | ok |
| MEDIUM | 1653 | 37.8% | 0.227 | ok |
| HIGH | 665 | 30.7% | 0.027 | ok |

*Confidence bucket verdict: non-monotonic*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
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
| stop | 1402 |
| target | 528 |
| time_stop | 486 |
| gap_skip_down | 107 |
| gap_skip_up | 13 |


## Non-winner Analysis

| Failure mode | Count | % |
|--------------|-------|---|
| Stop-out | 1402 | 90% |
| Time-stop | 148 | 10% |

*Stop-out dominated (90%) — setups are breaking down; the issue is setup quality rather than target distance.*


## Stop-out Forensics

| Metric | Value |
|--------|-------|
| Stop-outs | 1402 |
| % reached target post-stop | 13% |
| Median post-stop MFE | +0.30R |
| Winners' MAE near −1R (≤ −0.75) | 18% |

**Branch B** — 13% of stopped trades subsequently reached target (post-stop MFE median +0.30R) — stopped trades continued lower, consistent with genuine breakdown (Branch B: setups may lack edge at the current stop level → evaluate entry quality via E14.3/E14.4).


## Target Distance Analysis — by R-multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| 1.0–1.5×R | 335 | 38% | 0.115 |
| 1.5–2.0×R | 320 | 23% | -0.050 |
| 2.0–2.5×R | 273 | 20% | -0.029 |
| 2.5–3.0×R | 233 | 16% | 0.007 |
| 3.0+×R | 1035 | 11% | 0.355 |


## Target Distance Analysis — by ATR multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| <1.0 ATR | 98 | 73% | 0.060 |
| 1.0–1.5 ATR | 91 | 43% | -0.104 |
| 1.5–2.0 ATR | 466 | 37% | 0.109 |
| 2.0–2.5 ATR | 584 | 25% | 0.286 |
| 2.5+ ATR | 1177 | 9% | 0.149 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |
|------|---------------|----------------|----------------|------|----------------|---------|
| 200-MA distance in range | 478 | -0.078 | 0.161 | -0.239 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| At a logical support level | 648 | -0.030 | 0.161 | -0.191 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Debt/equity acceptable | 377 | -0.082 | 0.161 | -0.244 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Earnings clear | 179 | 0.081 | 0.161 | -0.080 | **CUT** | no measurable value in this sample |
| Liquidity | 165 | 0.221 | 0.161 | 0.059 | **CUT** | no measurable value in this sample |
| Market cap in range | 590 | 0.007 | 0.161 | -0.155 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Near 52w high in last 60d | 793 | 0.055 | 0.161 | -0.106 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Profitable | 54 | 1.772 | 0.161 | 1.611 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback depth | 821 | 0.101 | 0.161 | -0.060 | **CUT** | no measurable value in this sample |
| Pullback duration 1d | 49 | -0.146 | 0.161 | -0.308 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 21d | 97 | 0.528 | 0.161 | 0.367 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 22d | 83 | 0.062 | 0.161 | -0.099 | **CUT** | no measurable value in this sample |
| Pullback duration 23d | 84 | -0.065 | 0.161 | -0.227 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 24d | 77 | -0.284 | 0.161 | -0.446 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 25d | 67 | 0.013 | 0.161 | -0.149 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 26d | 69 | 0.353 | 0.161 | 0.192 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 27d | 70 | -0.138 | 0.161 | -0.299 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 28d | 70 | -0.179 | 0.161 | -0.341 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 29d | 78 | 0.330 | 0.161 | 0.168 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 2d | 108 | 0.018 | 0.161 | -0.144 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 30d | 82 | 0.371 | 0.161 | 0.210 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 31d | 81 | 0.081 | 0.161 | -0.080 | **CUT** | no measurable value in this sample |
| Pullback duration 32d | 83 | 0.042 | 0.161 | -0.119 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 33d | 80 | 0.381 | 0.161 | 0.219 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 34d | 74 | 0.058 | 0.161 | -0.103 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 35d | 70 | 0.513 | 0.161 | 0.352 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Pullback duration 36d | 76 | -0.178 | 0.161 | -0.339 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 37d | 81 | 0.025 | 0.161 | -0.136 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 38d | 88 | -0.180 | 0.161 | -0.342 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Pullback duration 39d | 142 | -0.164 | 0.161 | -0.326 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| RSI(14) reset | 141 | -0.088 | 0.161 | -0.250 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Relative strength vs SPY | 23 | 0.677 | 0.161 | 0.516 | **INSUFFICIENT-N** | insufficient n |
| SMA50 rising (20 sessions) | 135 | -0.506 | 0.161 | -0.667 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLB) above 50MA | 55 | 0.144 | 0.161 | -0.017 | **CUT** | no measurable value in this sample |
| Sector (XLC) above 50MA | 17 | 0.961 | 0.161 | 0.800 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLE) above 50MA | 83 | -0.028 | 0.161 | -0.190 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLF) above 50MA | 131 | -0.605 | 0.161 | -0.766 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLI) above 50MA | 85 | -0.113 | 0.161 | -0.274 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLK) above 50MA | 72 | 0.000 | 0.161 | -0.161 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLP) above 50MA | 62 | -0.074 | 0.161 | -0.235 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLRE) above 50MA | 71 | -0.054 | 0.161 | -0.216 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLU) above 50MA | 9 | -0.290 | 0.161 | -0.451 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLV) above 50MA | 85 | 0.181 | 0.161 | 0.020 | **CUT** | no measurable value in this sample |
| Sector (XLY) above 50MA | 112 | 0.099 | 0.161 | -0.063 | **CUT** | no measurable value in this sample |
| Swing low intact | 42 | 0.197 | 0.161 | 0.035 | **CUT** | no measurable value in this sample |
| Uptrend (SMA50 > SMA200) | 31 | 0.453 | 0.161 | 0.292 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Volume contraction | 4144 | 0.121 | 0.161 | -0.040 | **CUT** | no measurable value in this sample |
| Weekly above 30-MA | 6 | -0.284 | 0.161 | -0.445 | **INSUFFICIENT-N** | insufficient n |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.4% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 4.7% of simulated entries were skipped due to the opening price being outside the stop/target range.
