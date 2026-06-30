# Backtest Report

## Run Parameters

- Strategy: breakout
- Universe: 602 tickers
- Date range: 2024-01-01 → 2026-06-25
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 4247d20

## Summary Metrics

| Metric | Value |
|--------|-------|
| Trades | 85 |
| Win rate | 41.2% |
| Avg win (R) | 1.27 |
| Avg loss (R) | -0.97 |
| Expectancy (R) | -0.049 |
| Median hold (days) | 1 |
| Max drawdown (R) | 14.57 |


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 35 | 34.3% | -0.155 | ok |
| 55–69 | 22 | 45.5% | 0.176 | ok |
| 70–84 | 7 | 57.1% | 0.220 | insufficient n |
| 85–100 | 13 | 46.2% | -0.365 | insufficient n |

*Score bucket verdict: monotonically increasing*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 2 | 50.0% | 0.802 | insufficient n |
| MEDIUM | 61 | 45.9% | -0.065 | ok |
| HIGH | 22 | 27.3% | -0.085 | ok |

*Confidence bucket verdict: monotonically decreasing*


## Monthly Signal Counts (qualified)

| Month | Signals |
|-------|---------|
| 2024-01 | 6 |
| 2024-02 | 5 |
| 2024-03 | 7 |
| 2024-04 | 4 |
| 2024-05 | 3 |
| 2024-06 | 5 |
| 2024-08 | 2 |
| 2024-09 | 4 |
| 2024-10 | 4 |
| 2024-11 | 6 |
| 2024-12 | 7 |
| 2025-02 | 3 |
| 2025-03 | 2 |
| 2025-04 | 1 |
| 2025-06 | 5 |
| 2025-07 | 3 |
| 2025-09 | 4 |
| 2025-10 | 1 |
| 2026-01 | 2 |
| 2026-02 | 7 |
| 2026-03 | 3 |
| 2026-04 | 1 |
| 2026-05 | 4 |
| 2026-06 | 2 |


## Exit Reason Breakdown

| Reason | Count |
|--------|-------|
| stop | 48 |
| target | 32 |
| time_stop | 5 |
| gap_skip_up | 3 |
| gap_skip_down | 3 |


## Non-winner Analysis

| Failure mode | Count | % |
|--------------|-------|---|
| Stop-out | 48 | 96% |
| Time-stop | 2 | 4% |

*Stop-out dominated (96%) — setups are breaking down; the issue is setup quality rather than target distance.*


## Stop-out Forensics

| Metric | Value |
|--------|-------|
| Stop-outs | 48 |
| % reached target post-stop | 10% |
| Median post-stop MFE | +0.10R |
| Winners' MAE near −1R (≤ −0.75) | 14% |

**Branch B** — 10% of stopped trades subsequently reached target (post-stop MFE median +0.10R) — stopped trades continued lower, consistent with genuine breakdown (Branch B: setups may lack edge at the current stop level → evaluate entry quality via E14.3/E14.4).


## Target Distance Analysis — by R-multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| 1.0–1.5×R | 8 | 38% | -0.184 |
| 1.5–2.0×R | 7 | 14% | -0.627 |
| 2.0–2.5×R | 5 | 20% | -0.392 |
| 2.5–3.0×R | 7 | 29% | 0.084 |
| 3.0+×R | 26 | 12% | 0.156 |


## Target Distance Analysis — by ATR multiple

| Distance | n | Hit rate | E(R) |
|----------|---|----------|------|
| <1.0 ATR | 39 | 62% | -0.050 |
| 1.0–1.5 ATR | 5 | 40% | -0.301 |
| 1.5–2.0 ATR | 2 | 0% | -1.000 |
| 2.0–2.5 ATR | 1 | 0% | -1.000 |
| 2.5+ ATR | 38 | 16% | 0.060 |


## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |
|------|---------------|----------------|----------------|------|----------------|---------|
| ADX trend strength | 52 | -0.122 | -0.049 | -0.073 | **CUT** | no measurable value in this sample |
| BB squeeze | 313 | -0.145 | -0.049 | -0.096 | **CUT** | no measurable value in this sample |
| Consolidation breakout | 70 | -0.263 | -0.049 | -0.214 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Debt/equity acceptable | 19 | 0.061 | -0.049 | 0.111 | **INSUFFICIENT-N** | insufficient n |
| Earnings clear | 8 | -0.119 | -0.049 | -0.069 | **INSUFFICIENT-N** | insufficient n |
| Liquidity | 3 | 0.864 | -0.049 | 0.913 | **INSUFFICIENT-N** | insufficient n |
| Market cap in range | 34 | -0.393 | -0.049 | -0.344 | **KEEP** | near-misses underperform qualified (gate shows protective value) |
| Near 52w high | 59 | 0.447 | -0.049 | 0.496 | **CUT** | near-misses outperform qualified (gate may be blocking good setups) |
| Profitable | 1 | -1.000 | -0.049 | -0.951 | **INSUFFICIENT-N** | insufficient n |
| RSI in breakout range | 16 | 0.017 | -0.049 | 0.066 | **INSUFFICIENT-N** | insufficient n |
| Trend alignment | 1 | 1.635 | -0.049 | 1.684 | **INSUFFICIENT-N** | insufficient n |
| Volume confirmation | 366 | -0.107 | -0.049 | -0.058 | **CUT** | no measurable value in this sample |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 0.9% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 6.6% of simulated entries were skipped due to the opening price being outside the stop/target range.
