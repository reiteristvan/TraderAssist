# E14.4 — Loser Post-Mortem (pb_2024_2026_with_stoploss)

**Baseline:** 1623 qualified trades | 914 stop-outs | overall E(R) = +0.182R


## 25 High-Confidence Stop-outs (sorted by conf → score DESC)

_All fixed-stop exits carry exactly -1R; 'worst' here means highest-confidence setups that still failed — the cases most informative about what the strategy misses._

| # | Ticker | Date | Conf | Score | Regime | Dist 20MA | RS |
|---|--------|------|------|-------|--------|-----------|-----|
| 1 | CASH | 2025-05-30 | HIGH | 160 | BULLISH | -2.9% | 1.055 |
| 2 | FFBC | 2024-12-11 | HIGH | 150 | BULLISH | +0.7% | 1.076 |
| 3 | RXO | 2024-01-09 | HIGH | 148 | BULLISH | -2.3% | 1.071 |
| 4 | OPLN | 2025-06-20 | HIGH | 148 | BULLISH | -3.3% | 1.019 |
| 5 | TFIN | 2024-01-08 | HIGH | 145 | BULLISH | -1.9% | 1.129 |
| 6 | APAM | 2024-01-04 | HIGH | 142 | NEUTRAL | -0.9% | 1.105 |
| 7 | SLVM | 2024-09-09 | HIGH | 140 | BEARISH | -2.9% | 1.055 |
| 8 | NPK | 2025-07-24 | HIGH | 139 | BULLISH | +0.2% | 1.074 |
| 9 | BKU | 2024-12-13 | HIGH | 138 | BULLISH | -2.5% | 1.023 |
| 10 | NPK | 2025-07-25 | HIGH | 138 | BULLISH | +0.1% | 1.067 |
| 11 | FCF | 2024-12-16 | HIGH | 138 | BULLISH | -1.8% | 1.011 |
| 12 | BKU | 2024-12-16 | HIGH | 138 | BULLISH | -1.8% | 1.051 |
| 13 | SPNT | 2025-12-31 | HIGH | 138 | NEUTRAL | -0.7% | 1.180 |
| 14 | NPK | 2025-07-22 | HIGH | 137 | BULLISH | +2.0% | 1.091 |
| 15 | OTTR | 2024-05-24 | HIGH | 136 | BULLISH | +0.8% | 0.966 |
| 16 | UVV | 2024-01-08 | HIGH | 135 | BULLISH | -2.2% | 1.210 |
| 17 | MC | 2024-12-04 | HIGH | 135 | BULLISH | -0.2% | 1.087 |
| 18 | ALG | 2025-07-25 | HIGH | 134 | BULLISH | -0.6% | 1.131 |
| 19 | NPK | 2025-07-23 | HIGH | 134 | BULLISH | +1.7% | 1.087 |
| 20 | AGO | 2024-12-12 | HIGH | 134 | BULLISH | -1.0% | 1.037 |
| 21 | FCF | 2024-01-11 | HIGH | 132 | BULLISH | -4.0% | 1.072 |
| 22 | AESI | 2024-04-19 | HIGH | 132 | BEARISH | -2.1% | 1.310 |
| 23 | ACAD | 2026-01-05 | HIGH | 131 | BULLISH | -3.3% | 1.198 |
| 24 | MC | 2024-12-05 | HIGH | 131 | BULLISH | -0.7% | 1.104 |
| 25 | ALG | 2025-07-24 | HIGH | 131 | BULLISH | -1.6% | 1.117 |


## Pattern 1 — SPY Regime at Entry

| Regime | All trades | Worst stop-outs | Over-rep? |
|--------|-----------|-----------------|-----------|
| BULLISH | 85% | 84% | — |
| NEUTRAL | 7% | 8% | — |
| BEARISH | 8% | 8% | — |


## Pattern 2 — Distance Above 20-MA at Entry

| Bucket | All trades | Worst stop-outs | Over-rep? |
|--------|-----------|-----------------|-----------|
| <2% | 93% | 96% | — |
| 2–5% | 7% | 4% | — |
| 5–8% | 0% | 0% | — |
| >8% | 0% | 0% | — |


## Dimension Analysis — Expectancy and Stop-out Rate by Bucket (no gate applied)


### SPY Regime

| Bucket | n | E(R) | vs overall | Stop% | vs overall |
|--------|---|------|-----------|-------|-----------|
| BULLISH | 1373 | +0.167R | -0.015R | 56% | -0% |
| NEUTRAL | 121 | +0.210R | +0.028R | 55% | -2% |
| BEARISH | 129 | +0.313R | +0.131R | 63% | +6% |


### Distance Above 20-MA

| Bucket | n | E(R) | vs overall | Stop% | vs overall |
|--------|---|------|-----------|-------|-----------|
| <2% | 1503 | +0.196R | +0.014R | 58% | +2% |
| 2–5% | 119 | +0.013R | -0.169R | 30% | -26% |
| 5–8% | 1 | -0.271R | -0.453R | 0% | -56% |


### RS vs SPY

| Bucket | n | E(R) | vs overall | Stop% | vs overall |
|--------|---|------|-----------|-------|-----------|
| <0.95 | 113 | +0.568R | +0.386R | 58% | +2% |
| 0.95–1.05 | 573 | +0.206R | +0.024R | 57% | +1% |
| >1.05 | 937 | +0.121R | -0.061R | 56% | -1% |
