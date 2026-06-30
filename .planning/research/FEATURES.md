# Feature Research

**Domain:** Swing trading scanner — industry momentum display and winner/loser backtest analysis
**Researched:** 2026-06-30
**Confidence:** MEDIUM (websearch sources, cross-checked against codebase reality)

---

## Context: What Already Exists

Before the feature landscape, a grounding note on current state to prevent re-inventing
what is already built.

**Already shipped in scanner (do not re-build):**
- Sector-level momentum: `sector`, `sector_etf`, `sector_outperforming` on PullbackResult
- Sector gate: ETF above 50-day MA, outperforming SPY (pullback only — breakout has none)
- Score buckets, confidence buckets, gate attribution in report.py
- Failure analysis (stop_out vs time_stop), stop-out forensics (MAE/MFE branch A/B)
- Target distance analysis (R-multiple and ATR-multiple buckets)

**Gap addressed by this milestone:**
- Sector is 11 broad GICS buckets — too coarse. Industry group is finer (yfinance exposes
  `info['industry']`, ~60-80 categories). Same stock can be in a strong sector but a weak
  industry group.
- Backtest reports analyze *aggregate* performance and gate near-misses, but do NOT analyze
  *how individual entry-time metrics distribute across winners vs losers*.

---

## Feature Landscape

### Table Stakes — Industry Momentum Display

Features without which the display provides no decision value.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Industry group name | Traders need to know which group they are evaluating — "Semiconductor Equipment" vs "Regional Banks" changes the read entirely | LOW | yfinance `info['industry']` field; stored on signal |
| Industry 4-week performance vs SPY (%) | The single number that quantifies whether the industry has directional tailwind or headwind over a swing-trade-relevant window | MEDIUM | Requires computing an industry proxy: average return of universe peers in the same industry group over 20 trading days vs SPY return. Pure Python, no new data source |
| Industry momentum direction (Improving / Neutral / Declining) | Categorical label derived from performance trend — "Improving" means the 4-week RS is better than the 8-week RS; gives at-a-glance trend without requiring the trader to compute it | LOW | Derived from two lookback periods of the same computation; no extra data fetch |
| Top-half flag (boolean) | IBD's primary rule: buy stocks in industry groups ranked in the top half. A simple yes/no flag is the minimum actionable signal for a display-only field | LOW | Derived from ranking all industries in the universe by 4-week RS; flag is True if this industry's rank is in top 50% |

### Table Stakes — Winner vs Loser Analysis

Features without which the analysis cannot surface discriminating patterns.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-metric bucket table for each entry-time signal field | The only way to see whether RSI=42 entries win more than RSI=58 entries is to bucket them — a single aggregate win rate hides this entirely | MEDIUM | 4-5 bins per metric; win rate + expectancy per bin; reuses Trade objects already in simulate.py |
| Pullback discriminators: RSI, vol_contraction, pullback_depth_pct, distance_to_support_pct, rs_strength | These are the seven fields in PullbackResult that describe entry quality — without bucketing them, the analysis is blind to whether any of them correlates with outcomes | MEDIUM | All fields already stored in signals table; query by run_id, join with outcome |
| Breakout discriminators: vol_ratio, ADX, pct_to_52w_high, bb_width, RSI | Same rationale — BreakoutResult fields that describe entry quality | MEDIUM | Same approach as pullback |
| Median winner vs median loser comparison table | Simplest summary: "Median winner: RSI 51, vol_contraction 0.62. Median loser: RSI 54, vol_contraction 0.84." One row per metric. A trader can read this in 10 seconds | LOW | Compute median of each field split by r_multiple > 0 vs <= 0 |

### Differentiators — Industry Momentum Display

Features that go beyond minimum viable and add genuine competitive value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Industry rank (absolute, e.g., 7 of 43) | Gives the trader context: being 7th out of 43 industry groups is more informative than "Improving" alone. Matches IBD's rank-based mental model that swing traders already use | MEDIUM | Requires consistent universe grouping per scan date; rank among all industries represented in the current universe file |
| Rank delta vs 4 weeks prior (e.g., +5 or -3) | Shows acceleration or deceleration of momentum — an industry moving from rank 30 to rank 7 in four weeks is categorically different from one at rank 7 for a year | MEDIUM | Store historical rank snapshots; or compute from two separate windows |
| Industry 4-week RS score formatted as a single number (e.g., 1.08 = 8% outperformance vs SPY) | The same RS metric already used for individual stocks, applied at the industry level. Traders who already read RS = 1.12 for a stock immediately understand RS = 1.06 for its industry | LOW | Same `_rs_metrics` computation applied to the industry proxy return vs SPY |
| Industry momentum at entry stored on Signal/Trade for backtest lookup | This is the bridge to winner/loser analysis — without storing industry momentum at signal time, you cannot later ask "did signals in top-quartile industries win more?" | MEDIUM | Add `industry_rs` and `industry_rank` columns to signals table; schema v7 bump |

### Differentiators — Winner vs Loser Analysis

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Industry momentum at entry as a discriminating variable | The core hypothesis of this milestone: signals in industries with RS > 1.05 may have meaningfully different win rates than signals in industries with RS < 0.95. Only testable if industry momentum is stored at signal time (see dependency below) | MEDIUM | Depends on industry_rs being stored on Trade; bucket by industry_rs quartile |
| Score component contribution analysis | The current score formula has ~12 additive components. Bucketing win rate by individual score components (not just total score) reveals which components actually predict outcomes vs which are noise | MEDIUM | Requires storing component values at signal time or recomputing from stored gate_detail_json |
| Formatted comparison: "Winners vs Losers" side-by-side table in report.md | The markdown report already has a standard table format. Adding a W/L comparison section with each metric's median Winner value vs median Loser value in two columns gives traders an immediately scannable pattern summary | LOW | Pure computation + rendering addition to render_report() |
| Minimum sample size guard (n >= 30 per bin) | Without this guard, a bin with 3 trades that all won will show 100% win rate and mislead. The existing MIN_BUCKET_N = 20 pattern already enforces this elsewhere — apply consistently to W/L analysis | LOW | Copy the existing MIN_BUCKET_N pattern from report.py |

### Anti-Features

Features that are commonly considered but should not be built.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Hard gate on industry momentum | Seems like a natural extension of the sector gate | The project constraint is explicit: display-only until backtest evidence supports gating. ADX gate removal degraded performance; gate changes require data, not intuition | Store the field, run the W/L analysis, then decide — this is the milestone's stated sequence |
| IBD 197 industry group classification | IBD's granularity seems ideal | Proprietary classification unavailable via yfinance. Building a 197-group replica requires a curated ticker-to-group mapping table that does not exist in the codebase and cannot be derived automatically | Use yfinance `info['industry']` (~60-80 categories) which is finer than GICS sectors and freely available |
| Machine learning feature importance | Would give "scientific" discriminating feature ranking | With ~200-500 qualified trades per backtest run, any ML result will have wide confidence intervals and invite curve-fitting. The sample sizes are too small for reliable ML-based feature selection | Use simple bucketing (5 bins per metric) and report actual n per bin — honest about sample size constraints |
| Industry ETF price as a gate input | Sector ETF gate already uses this for sectors; applying it to 60+ industries seems consistent | Most sub-industry ETFs have lower liquidity, higher tracking error, and may not be available for all yfinance-recognized industries | Use peer performance (stocks in the same industry already in the universe file) as the industry proxy — more reliable, no new external dependency |
| Real-time industry rank recalculation during live scan | Freshness seems valuable | The scanner runs nightly on daily bars. Industry rank computed from yesterday's closes is sufficient. Real-time recalculation adds latency with no meaningful accuracy gain | Compute once per scan run and attach to each signal in that run |
| Cross-metric interaction effects (e.g., RSI AND vol_contraction combined) | Would reveal compound patterns | Requires 2x the trades per cell (e.g., 5 RSI bins × 5 vol_contraction bins = 25 cells needing 30 trades each = 750 trades minimum). Current run sizes cannot fill this reliably | Report individual metric buckets first; revisit interaction analysis only if sample sizes grow to 1000+ qualified trades |

---

## Feature Dependencies

```
Industry group name (yfinance info['industry'])
    └──required by──> Industry 4-week RS score
    └──required by──> Industry rank (absolute)
    └──required by──> Top-half flag
    └──required by──> Industry momentum direction

Industry 4-week RS score
    └──required by──> Industry rank (rank is ordering of RS scores)
    └──required by──> Rank delta (delta requires two historical rank snapshots)
    └──required by──> Industry momentum at entry on Trade object

Industry momentum at entry on Trade object
    └──required by──> Industry momentum as W/L discriminating variable
    └──required by──> Industry bucket analysis in report

Per-metric bucket table (pullback/breakout fields)
    └──enhances──> Median winner vs median loser table (same data, different view)
    └──required for──> Score component contribution analysis (component values needed)

Schema bump (signals table: add industry_group, industry_rs, industry_rank)
    └──required by──> All industry display features in report and UI
    └──required by──> Industry momentum at entry on Trade object
```

### Dependency Notes

- **Industry name is the root dependency:** All momentum computations require knowing which industry the stock belongs to. yfinance `info['industry']` is the only free source. Must be fetched alongside quality data in `earnings_store.py` / quality loading path, not on every scan.

- **Industry RS requires a peer group:** Computing a stock's industry RS requires finding other stocks in the same industry within the universe file. This means the computation must happen at run_scan() time when the full universe is loaded, not inside the pure `evaluate()` function (which must stay free of external data).

- **Schema bump is a prerequisite:** Storing industry fields on signals requires `schema_version` bump to 7 and migration SQL. This is a single blocking dependency for the entire feature set — nothing can be persisted until the schema change ships.

- **W/L analysis of industry momentum depends on industry being stored at signal time:** If industry_rs is not stored on the signal, historical backtest runs cannot be analyzed. This means the schema change and industry computation must ship *before* the first backtest run whose W/L data you want to analyze.

---

## MVP Definition

### Launch With (v1)

Minimum to validate the hypothesis that industry momentum correlates with outcomes.

- [ ] Industry group name stored on every signal (pullback + breakout) — the root enabling field
- [ ] Industry 4-week RS score computed at scan time, stored on signal — the quantitative measure
- [ ] Top-half flag (boolean) derived from RS score ranking — the at-a-glance decision aid
- [ ] Industry momentum direction (Improving / Neutral / Declining) — human-readable trend
- [ ] Schema v7 migration adding `industry_group`, `industry_rs`, `industry_rank`, `industry_top_half` to signals
- [ ] Per-metric bucket tables in backtest report for pullback (RSI, vol_contraction, pullback_depth_pct, rs_strength) and breakout (vol_ratio, ADX, pct_to_52w_high)
- [ ] Median winner vs median loser comparison table in report.md

### Add After Validation (v1.x)

Add once the v1 data has been collected from at least one full backtest run.

- [ ] Industry rank absolute position (1 of N) — add once we know how many unique industry groups appear in the universe
- [ ] Rank delta vs 4 weeks prior — requires two scan dates of data to be meaningful
- [ ] Industry momentum bucket in W/L analysis — can only be done after industry_rs has been stored on historical signals; trigger: first full backtest run with v7 schema

### Future Consideration (v2+)

Defer until pattern is confirmed or sample sizes grow.

- [ ] Score component contribution analysis — requires recomputing components from gate_detail_json; high complexity, defer until W/L analysis confirms a useful signal
- [ ] Industry cohort analysis by market regime — interesting but requires regime labels on all historical signals; low priority until basic W/L analysis yields a finding
- [ ] UI display of industry momentum fields — the Angular UI does not yet show these; add to signal detail view after CLI/report validation confirms the fields are worth showing

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Industry group name on signal | HIGH | LOW (yfinance info field) | P1 |
| Industry 4-week RS score | HIGH | MEDIUM (peer aggregation logic) | P1 |
| Top-half flag | HIGH | LOW (derived from RS score) | P1 |
| Industry momentum direction | MEDIUM | LOW (derived from two RS windows) | P1 |
| Schema v7 migration | HIGH (blocker) | LOW | P1 |
| Per-metric bucket tables in report | HIGH | MEDIUM | P1 |
| Median winner vs loser table | HIGH | LOW | P1 |
| Industry rank absolute | MEDIUM | MEDIUM | P2 |
| Rank delta | MEDIUM | MEDIUM | P2 |
| Industry momentum bucket in W/L analysis | HIGH | LOW (after schema ships) | P2 |
| Score component contribution | LOW | HIGH | P3 |
| UI display of industry fields | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Required for the milestone to deliver its stated hypothesis-validation value
- P2: Adds depth after v1 data is collected
- P3: Future enhancement, not needed to answer the hypothesis

---

## Competitor Feature Analysis

| Feature | IBD MarketSmith / MarketSurge | TC2000 / Finviz | TraderAssist Approach |
|---------|------------------------------|------------------|-----------------------|
| Industry grouping | 197 proprietary groups, ranked 1-197 | GICS sectors and sub-industries | yfinance `info['industry']` (~60-80 groups); finer than GICS sector, coarser than IBD |
| Relative strength display | RS Rating 1-99 (52-week vs all stocks) + RS Line chart overlay | RS% vs S&P over configurable period | 4-week RS score (outperformance ratio vs SPY); consistent with existing `rs_strength` field on PullbackResult |
| Rank trend | Current rank + rank 3 months and 6 months ago | Not typically shown | Rank delta vs 4 weeks prior (v1.x) |
| Winner/loser analysis | Not a feature — IBD is a scanner, not a backtester | Not present | Core differentiator: per-metric bucket tables + median W/L comparison integrated into existing backtest report |
| Minimum threshold | Top 40 of 197 (top 20%) for buys | N/A | Top-half flag (top 50%) for display-only v1; threshold can tighten once data shows what works |

---

## Sources

- IBD/MarketSmith industry group ranking methodology and RS display format (websearch, MEDIUM confidence)
- Quantitative breakout strategy research: volume ratio as primary discriminator, ADX surge pattern (websearch, MEDIUM confidence)
- Pullback strategy entry quality research: RSI window, volume contraction, support proximity (websearch, MEDIUM confidence)
- Winner/loser MAE/MFE analysis methodology from trade journal tools (websearch, MEDIUM confidence)
- TraderAssist codebase: PullbackResult, BreakoutResult, report.py, store_db.py (direct inspection, HIGH confidence)

---
*Feature research for: swing trading scanner — industry momentum display and winner/loser backtest analysis*
*Researched: 2026-06-30*
