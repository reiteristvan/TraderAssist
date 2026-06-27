# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 602 tickers
- Date range: 2026-01-01 → 2026-06-25
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 6349b67

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 327 |
| Win rate | 44.6% |
| Avg win (R) | 2.21 |
| Avg loss (R) | -0.95 |
| Expectancy (R) | 0.460 |
| Median hold (days) | 5 |
| Max drawdown (R) | 63.43 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 0 | — | — | insufficient n |
| 70–84 | 15 | 53.3% | 0.345 | insufficient n |
| 85–100 | 308 | 43.8% | 0.466 | ok |

*Score bucket verdict: insufficient data for verdict*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 30 | 23.3% | -0.517 | ok |
| MEDIUM | 239 | 45.2% | 0.535 | ok |
| HIGH | 58 | 53.4% | 0.659 | ok |

*Confidence bucket verdict: monotonically increasing*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
| 2026-01 | 90 |
| 2026-02 | 30 |
| 2026-03 | 34 |
| 2026-04 | 21 |
| 2026-05 | 138 |
| 2026-06 | 32 |


## Exit Reason Breakdown

| Reason | Count |
|--------|-------|
| stop | 165 |
| target | 87 |
| time_stop | 75 |
| gap_skip_down | 16 |
| gap_skip_up | 2 |


## Non-winner Analysis

| Failure mode | Count | % |
|--------------|-------|---|
| Stop-out | 165 | 91% |
| Time-stop | 16 | 9% |

*Stop-out dominated (91%) — setups are breaking down; the issue is setup quality rather than target distance.*


## Stop-out Forensics

| Metric | Value |
|--------|-------|
| Stop-outs | 165 |
| % reached target post-stop | 13% |
| Median post-stop MFE | +0.68R |
| Winners' MAE near −1R (≤ −0.75) | 16% |

**Branch B** — 13% of stopped trades subsequently reached target (post-stop MFE median +0.68R) — stopped trades continued lower, consistent with genuine breakdown (Branch B: setups may lack edge at the current stop level → evaluate entry quality via E14.3/E14.4).


## Target Distance Analysis — by R-multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| 1.0–1.5×R | 31 | 42% | 0.235 |
| 1.5–2.0×R | 47 | 21% | -0.006 |
| 2.0–2.5×R | 37 | 24% | 0.089 |
| 2.5–3.0×R | 27 | 26% | 0.552 |
| 3.0+×R | 151 | 17% | 0.794 |


## Target Distance Analysis — by ATR multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| <1.0 ATR | 20 | 75% | 0.005 |
| 1.0–1.5 ATR | 15 | 47% | -0.076 |
| 1.5–2.0 ATR | 58 | 40% | 0.287 |
| 2.0–2.5 ATR | 90 | 30% | 0.696 |
| 2.5+ ATR | 144 | 10% | 0.502 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |
|------|---------------|----------------|----------------|------|----------------|---------|
| 200-MA distance in range | 89 | -0.171 | 0.460 | -0.631 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| At a logical support level | 85 | -0.416 | 0.460 | -0.877 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Debt/equity acceptable | 44 | -0.041 | 0.460 | -0.501 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Earnings clear | 26 | 0.186 | 0.460 | -0.274 | **INSUFFICIENT-N** | insufficient n |
| Liquidity | 25 | -0.134 | 0.460 | -0.594 | **INSUFFICIENT-N** | insufficient n |
| Market cap in range | 96 | 0.099 | 0.460 | -0.362 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Near 52w high in last 60d | 95 | 0.227 | 0.460 | -0.234 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Profitable | 27 | 1.307 | 0.460 | 0.846 | **INSUFFICIENT-N** | insufficient n |
| Pullback depth | 210 | 0.536 | 0.460 | 0.076 | **CUT** | no measurable value in this sample |
| Pullback duration 1d | 8 | 0.156 | 0.460 | -0.304 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 21d | 19 | 0.193 | 0.460 | -0.267 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 22d | 10 | 0.490 | 0.460 | 0.030 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 23d | 14 | 1.473 | 0.460 | 1.013 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 24d | 10 | 0.489 | 0.460 | 0.029 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 25d | 7 | 0.646 | 0.460 | 0.186 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 26d | 10 | 0.594 | 0.460 | 0.134 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 27d | 7 | 0.383 | 0.460 | -0.077 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 28d | 7 | 0.479 | 0.460 | 0.018 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 29d | 6 | 0.923 | 0.460 | 0.463 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 2d | 14 | 0.398 | 0.460 | -0.062 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 30d | 4 | -1.000 | 0.460 | -1.460 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 31d | 4 | 0.350 | 0.460 | -0.111 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 32d | 7 | -0.046 | 0.460 | -0.507 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 33d | 7 | -0.457 | 0.460 | -0.917 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 34d | 6 | -1.000 | 0.460 | -1.460 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 35d | 6 | 0.144 | 0.460 | -0.316 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 36d | 5 | -1.000 | 0.460 | -1.460 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 37d | 5 | -0.700 | 0.460 | -1.161 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 38d | 6 | -0.166 | 0.460 | -0.627 | **INSUFFICIENT-N** | insufficient n |
| Pullback duration 39d | 8 | 0.531 | 0.460 | 0.070 | **INSUFFICIENT-N** | insufficient n |
| RSI(14) reset | 20 | -0.202 | 0.460 | -0.662 | **INSUFFICIENT-N** | insufficient n |
| Relative strength vs SPY | 12 | -0.203 | 0.460 | -0.663 | **INSUFFICIENT-N** | insufficient n |
| SMA50 rising (20 sessions) | 16 | 0.537 | 0.460 | 0.077 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLB) above 50MA | 7 | -0.142 | 0.460 | -0.602 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLC) above 50MA | 8 | -0.408 | 0.460 | -0.868 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLE) above 50MA | 28 | 0.013 | 0.460 | -0.448 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLF) above 50MA | 86 | -0.853 | 0.460 | -1.314 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Sector (XLI) above 50MA | 6 | -1.000 | 0.460 | -1.460 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLK) above 50MA | 19 | -0.143 | 0.460 | -0.603 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLP) above 50MA | 19 | -0.729 | 0.460 | -1.189 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLRE) above 50MA | 13 | 1.242 | 0.460 | 0.781 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLU) above 50MA | 4 | 0.308 | 0.460 | -0.152 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLV) above 50MA | 27 | -0.302 | 0.460 | -0.762 | **INSUFFICIENT-N** | insufficient n |
| Sector (XLY) above 50MA | 22 | -0.462 | 0.460 | -0.922 | **INSUFFICIENT-N** | insufficient n |
| Uptrend (SMA50 > SMA200) | 9 | 0.706 | 0.460 | 0.245 | **INSUFFICIENT-N** | insufficient n |
| Volume contraction | 685 | 0.408 | 0.460 | -0.052 | **CUT** | no measurable value in this sample |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 1.2% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 5.2% of simulated entries were skipped due to the opening price being outside the stop/target range.
