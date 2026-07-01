# Requirements: TraderAssist — Signal Quality Milestone

**Defined:** 2026-06-30
**Core Value:** Surface high-quality swing trade setups where the signal has a genuine edge — not just gate compliance.

## v1 Requirements

### Industry Momentum

- [x] **IND-01**: Every signal shows the industry group name (e.g. "Software—Infrastructure") from yfinance `info['industry']`
- [x] **IND-02**: Every signal shows a 20-day momentum score (signed % outperformance vs SPY) for the stock's industry group ETF
- [x] **IND-03**: Every signal shows an above/below 50-day MA boolean flag for the industry ETF (trending up or not)
- [x] **IND-04**: Every signal shows an industry rank expressed as a top-N% percentile among all industry groups observed in the scan universe
- [x] **IND-05**: Industry momentum fields are stored in dedicated columns (`industry_group`, `industry_momentum`) in the signals table under schema v9
- [x] **IND-06**: Industry momentum is computed without look-ahead bias — ETF price data is anchored to the signal's `as_of` date using the same sliced-market pattern as SPY in the backtest loop
- [x] **IND-07**: Industry momentum fields appear in scan CLI output and are visible in the web UI signal table

### Winner/Loser Analysis

- [x] **WLA-01**: Backtest reports include a winner/loser characteristic analysis section showing median entry-time metric values for winners vs losers
- [x] **WLA-02**: Analysis covers at minimum 6 entry metrics: RSI at entry, volume ratio (RVOL), pullback depth %, ATR multiple, industry momentum score, and pct to 52-week high
- [x] **WLA-03**: Analysis is produced separately for pullback and breakout strategies (not combined)
- [x] **WLA-04**: Industry momentum is included as one of the discriminating dimensions in the winner/loser analysis
- [x] **WLA-05**: Analysis includes a cell-size gate — any bucket with fewer than 50 trades displays a warning rather than a potentially spurious finding
- [x] **WLA-06**: The feature list analyzed is pre-registered in code (fixed list, not exploratory) to prevent multiple-comparisons overfitting

## v2 Requirements

### Industry Momentum — Extended Display

- **IND-EXT-01**: Industry rank delta vs 4 weeks prior (momentum-of-momentum)
- **IND-EXT-02**: Top-quartile flag prominently highlighted in UI

### Industry Momentum — Gate Promotion

- **IND-GATE-01**: Industry momentum promoted to a hard gate (signals with weak industry blocked from qualifying) — only after backtest evidence from this milestone demonstrates discriminating value

### Winner/Loser Analysis — Extended

- **WLA-EXT-01**: Statistical significance indicator (p-value or confidence interval) on each discriminating metric
- **WLA-EXT-02**: Time-series view of win rate by quarter to detect regime dependency

## Out of Scope

| Feature | Reason |
|---------|--------|
| Changing existing pullback/breakout gates | Stable; do not touch without new empirical evidence — key lesson from ADX and volume contraction reversals |
| Signal ranking / top-N selection | Not the current focus; display-and-validate first |
| Macro timing rules (FOMC, earnings season) | Not prioritized for this milestone |
| IBD-style 197-group classification | Proprietary; not available via yfinance |
| Industry momentum as a gate (v1) | Display-only first; IND-GATE-01 is v2 contingent on evidence |
| Paid data feeds (Bloomberg, Refinitiv) | yfinance-only constraint; no paid feeds |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| IND-01 | Phase 1 | Complete |
| IND-02 | Phase 2 | Complete |
| IND-03 | Phase 2 | Complete |
| IND-04 | Phase 2 | Complete |
| IND-05 | Phase 2 | Complete |
| IND-06 | Phase 2 | Complete |
| IND-07 | Phase 3 | Complete |
| WLA-01 | Phase 4 | Complete |
| WLA-02 | Phase 4 | Complete |
| WLA-03 | Phase 4 | Complete |
| WLA-04 | Phase 4 | Complete |
| WLA-05 | Phase 4 | Complete |
| WLA-06 | Phase 4 | Complete |

**Coverage:**

- v1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-30*
*Last updated: 2026-06-30 after roadmap creation*
