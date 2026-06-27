# Backtest Report

## Run Parameters

- Strategy: pullback
- Universe: 503 tickers
- Date range: 2024-01-01 → 2026-06-25
- Earnings gate: on
- Time stop: 10 sessions
- Entry: next_open
- Git hash: 6349b67

## Summary Metrics

*No qualifying trades in this run.*


## Score Buckets (qualified trades only)

| Score range | n | Win rate | Expectancy (R) | Verdict |
|-------------|---|----------|----------------|---------|
| 40–54 | 0 | — | — | insufficient n |
| 55–69 | 0 | — | — | insufficient n |
| 70–84 | 0 | — | — | insufficient n |
| 85–100 | 0 | — | — | insufficient n |

*Score bucket verdict: insufficient data for verdict*


## Confidence Buckets (qualified trades only)

| Confidence | n | Win rate | Expectancy (R) | Verdict |
|------------|---|----------|----------------|---------|
| LOW | 0 | — | — | insufficient n |
| MEDIUM | 0 | — | — | insufficient n |
| HIGH | 0 | — | — | insufficient n |

*Confidence bucket verdict: insufficient data for verdict*


## Monthly Signal Counts (qualified)

*No monthly data.*


## Exit Reason Breakdown



## Gate Attribution (near-miss analysis)

| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |
|------|---------------|----------------|----------------|------|----------------|---------|
| Market cap in range | 1992 | nan | 0.000 | nan | **KEEP** | near-misses underperform qualified (gate shows protective value) |


## Known Biases

**Survivorship bias** — universe contains currently-listed names only; delisted/bankrupt names are absent. Results are optimistic relative to the real investable universe at each historical date.

**Look-ahead bias (fundamentals)** — quality fields (market cap, profitability, debt/equity, sector) reflect present-day values applied to all historical dates. A name that went from small-cap to mid-cap during the backtest period may have been misclassified in early dates.

**Earnings gate skip rate** — 0.0% of signals had no earnings data and were evaluated without the earnings-proximity gate.

**Gap-skip rate** — 0.0% of simulated entries were skipped due to the opening price being outside the stop/target range.
