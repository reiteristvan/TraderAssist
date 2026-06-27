# E14.4 — Loser Post-Mortem (pb_2024_2026_gate_cut_long)

**Baseline:** 6506 qualified trades | 3636 stop-outs | overall E(R) = +0.140R


## 25 Worst Stop-outs

| # | Ticker | Date | R | Regime | Dist 20MA | RS |
|---|--------|------|---|--------|-----------|-----|
| 1 | APLE | 2024-01-02 | -1.00R | BULLISH | +0.2% | 1.024 |
| 2 | CARG | 2024-01-02 | -1.00R | BULLISH | +1.6% | 1.228 |
| 3 | EPAC | 2024-01-02 | -1.00R | BULLISH | +1.5% | 1.008 |
| 4 | FBP | 2024-01-02 | -1.00R | BULLISH | +0.1% | 1.074 |
| 5 | FUL | 2024-01-02 | -1.00R | BULLISH | -0.7% | 1.026 |
| 6 | GSHD | 2024-01-02 | -1.00R | BULLISH | -1.7% | 0.935 |
| 7 | KAI | 2024-01-02 | -1.00R | BULLISH | -0.3% | 1.085 |
| 8 | MTUS | 2024-01-02 | -1.00R | BULLISH | +3.4% | 0.995 |
| 9 | PRLB | 2024-01-02 | -1.00R | BULLISH | -0.9% | 1.317 |
| 10 | RXO | 2024-01-02 | -1.00R | BULLISH | +1.9% | 1.100 |
| 11 | SLVM | 2024-01-02 | -1.00R | BULLISH | -1.5% | 1.056 |
| 12 | SPSC | 2024-01-02 | -1.00R | BULLISH | -2.1% | 0.993 |
| 13 | UPWK | 2024-01-02 | -1.00R | BULLISH | -1.8% | 1.193 |
| 14 | VECO | 2024-01-02 | -1.00R | BULLISH | +1.6% | 1.013 |
| 15 | YELP | 2024-01-02 | -1.00R | BULLISH | +1.0% | 0.996 |
| 16 | ALG | 2024-01-03 | -1.00R | BULLISH | +0.1% | 1.060 |
| 17 | APAM | 2024-01-03 | -1.00R | BULLISH | -1.0% | 1.087 |
| 18 | APLE | 2024-01-03 | -1.00R | BULLISH | -0.2% | 1.037 |
| 19 | ARCB | 2024-01-03 | -1.00R | BULLISH | +1.2% | 1.077 |
| 20 | CATY | 2024-01-03 | -1.00R | BULLISH | +0.9% | 1.149 |
| 21 | CHCO | 2024-01-03 | -1.00R | BULLISH | +0.2% | 1.084 |
| 22 | CRGY | 2024-01-03 | -1.00R | BULLISH | +3.5% | 1.058 |
| 23 | CVCO | 2024-01-03 | -1.00R | BULLISH | -2.2% | 1.145 |
| 24 | HTH | 2024-01-03 | -1.00R | BULLISH | -0.8% | 1.086 |
| 25 | HWKN | 2024-01-03 | -1.00R | BULLISH | -1.0% | 1.038 |


## Pattern 1 — SPY Regime at Entry

| Regime | All trades | Worst stop-outs | Over-rep? |
|--------|-----------|-----------------|-----------|
| BULLISH | 84% | 100% | — |
| NEUTRAL | 7% | 0% | — |
| BEARISH | 9% | 0% | — |


## Pattern 2 — Distance Above 20-MA at Entry

| Bucket | All trades | Worst stop-outs | Over-rep? |
|--------|-----------|-----------------|-----------|
| <2% | 91% | 92% | — |
| 2–5% | 9% | 8% | — |
| 5–8% | 1% | 0% | — |
| >8% | 0% | 0% | — |


## Dimension Analysis — Expectancy by Bucket (no gate applied)


### SPY Regime

| Bucket | n | E(R) | vs overall |
|--------|---|------|-----------|
| BULLISH | 5464 | +0.131R | -0.009R |
| NEUTRAL | 458 | +0.258R | +0.118R |
| BEARISH | 584 | +0.128R | -0.012R |


### Distance Above 20-MA

| Bucket | n | E(R) | vs overall |
|--------|---|------|-----------|
| <2% | 5896 | +0.142R | +0.002R |
| 2–5% | 574 | +0.116R | -0.024R |
| 5–8% | 34 | +0.144R | +0.004R |
| >8% | 2 | +0.157R | +0.017R |


### RS vs SPY

| Bucket | n | E(R) | vs overall |
|--------|---|------|-----------|
| <0.95 | 540 | +0.379R | +0.239R |
| 0.95–1.05 | 2730 | +0.118R | -0.022R |
| >1.05 | 3236 | +0.118R | -0.022R |
