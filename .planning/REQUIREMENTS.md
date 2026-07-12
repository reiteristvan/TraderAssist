# Requirements — v1.1 Weekly Seasonality Analyzer

## v1 Requirements

### Sector Resolution

- [x] **SEAS-01**: User can filter a universe (sp500/sp400/sp600/all) down to tickers in a given GICS sector, matched case-insensitively, via a persisted ticker→sector cache
- [x] **SEAS-02**: If the sector name doesn't match any known GICS sector, the script fails with a clear error listing valid sector names

### Data Handling

- [x] **SEAS-03**: Script reuses the existing OHLCV cache (`data_store.get_history`) for daily adjusted close, falling back to yfinance only on cache miss
- [x] **SEAS-04**: Tickers with less than 2 years of history in the lookback window are skipped, with skipped tickers and count logged
- [x] **SEAS-05**: A missing/corrupt ticker cache file does not abort the run — it's skipped and logged like any other data gap

### Seasonality Statistics

- [x] **SEAS-06**: Daily log returns are aggregated by ISO calendar week (1–52), with week 53 merged into week 52, reporting mean/median/std daily return (bps), n_obs, and n_years per week
- [x] **SEAS-07**: Each week's mean daily return is reported as a delta vs. the full-sample baseline mean daily return
- [x] **SEAS-08**: A year-block bootstrap (resample years with replacement, preserving each year's full ticker-day cross-section) produces a 95% CI per week for the delta vs. baseline, controlled by `--bootstrap-iters` and `--seed` for reproducibility
- [x] **SEAS-09**: A week is flagged significant only when its 95% CI excludes zero — no tuning to manufacture significance

### Output

- [x] **SEAS-10**: CLI prints a 52-row table (week, mean_daily_ret_bps, delta_vs_baseline_bps, ci_low_bps, ci_high_bps, median_bps, n_obs, n_years, significant) to stdout, sorted by week
- [x] **SEAS-11**: CLI prints a summary: baseline mean, list of significant weeks (or "none — no week deviates significantly from baseline"), and the 5 highest/lowest weeks by delta with an explicit multiple-comparison caveat
- [x] **SEAS-12**: CLI prints a one-line survivorship-bias warning in the output header
- [x] **SEAS-13**: `--output` writes the results table to CSV when given; stdout output always happens regardless

### Verification

- [x] **SEAS-14**: A synthetic-data test with an injected -30bps week-28 effect across all years causes the script to flag week 28 as significant
- [x] **SEAS-15**: A synthetic-data test on pure noise flags approximately 0–3 of 52 weeks as significant (5% false-positive rate expectation), not more

## Future Requirements

(None deferred from this milestone — see PROJECT.md Active section for pre-existing v2 deferred items from v1.0: IND-GATE-01, IND-EXT-01, WLA-EXT-01, WLA-EXT-02, unrelated to this milestone.)

## Out of Scope

- **Wiring seasonality into the nightly scan/backtest pipeline** — this is a standalone diagnostic script, not a gate or scoring input; no schema_version bump, no changes to gate logic
- **Sub-sector/industry-level seasonality** — GICS sector granularity only for this milestone; industry-level seasonality would need the same ETF-proxy-style design work as v1.0's industry momentum feature, not assumed here
- **Web UI display of seasonality results** — CLI + CSV only; no Express API or Angular changes
- **Historical (delisted) tickers** — current index constituents only; survivorship bias is documented via a warning, not corrected

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEAS-01 | Phase 5 | Complete |
| SEAS-02 | Phase 5 | Complete |
| SEAS-03 | Phase 5 | Complete |
| SEAS-04 | Phase 5 | Complete |
| SEAS-05 | Phase 5 | Complete |
| SEAS-06 | Phase 6 | Complete |
| SEAS-07 | Phase 6 | Complete |
| SEAS-08 | Phase 6 | Complete |
| SEAS-09 | Phase 6 | Complete |
| SEAS-10 | Phase 7 | Complete |
| SEAS-11 | Phase 7 | Complete |
| SEAS-12 | Phase 7 | Complete |
| SEAS-13 | Phase 7 | Complete |
| SEAS-14 | Phase 6 | Complete |
| SEAS-15 | Phase 6 | Complete |

**Coverage:** 15/15 v1 requirements mapped ✓
