# Project Research Summary

**Project:** TraderAssist -- Industry Momentum Milestone
**Domain:** Python swing trading scanner -- industry/sector momentum display + winner/loser backtest analysis
**Researched:** 2026-06-30
**Confidence:** MEDIUM-HIGH (architecture HIGH from direct codebase reading; stack/features MEDIUM from community sources; pitfalls HIGH)

## Executive Summary

This milestone adds two capabilities to the existing TraderAssist swing scanner: (1) an industry-group momentum display field on every signal, giving traders a finer-grained tailwind/headwind read than the current 11-sector view, and (2) a winner/loser characteristic analysis in backtest reports that buckets entry-time signal metrics against outcomes. Both features are display/analysis only -- the explicit constraint from PROJECT.md is that no gates change without backtest evidence, and this milestone exists to collect that evidence.

The recommended approach builds directly on existing patterns. SECTOR_ETF_MAP and _sector_strength() in core.py are extended with a parallel INDUSTRY_ETF_MAP and _industry_momentum() helper; industry ETF symbols are added to data_store._MARKET_SYMBOLS so the Parquet cache handles refresh automatically; and the ath_zone field is the exact integration precedent -- computed in the post-evaluation block of run_scan() and generate_signals(), stored as a dedicated nullable column, passed through the Express API via SELECT *, and displayed in Angular. Schema version must be bumped to v7 with dedicated industry and industry_momentum columns.

The dominant risks are look-ahead bias (industry ETF prices not sliced to as_of in the backtest loop), overfitting via multiple comparisons in the winner/loser analysis (the same failure mode that caused the ADX and volume-contraction gate reversals), and insufficient cell sizes when the backtest trade corpus is split into subgroups. All three are preventable: anchor ETF price lookups to the existing sliced_market pattern, pre-register the feature list before analysing results, and enforce a minimum of 50 trades per cell before surfacing any finding.

---

## Conflict Resolution: gate_detail_json vs. Schema v7

**STACK.md position:** Store industry momentum in gate_detail_json (no schema bump) for the display-only phase.

**FEATURES.md position:** Schema v7 with dedicated columns is the single blocking dependency for the milestone.

**Recommendation: dedicated columns, schema v7.** Rationale:

1. **Queryability is required.** The winner/loser analysis must GROUP BY industry momentum buckets in SQL. Parsing JSON blobs in SQLite for 10,000+ rows cannot leverage indexes and was never designed as an analytical layer.
2. **The ath_zone precedent.** ARCHITECTURE.md explicitly cites ath_zone as the integration template. ath_zone is a dedicated nullable column added via a prior migration. Follow the same pattern.
3. **store_db.py policy.** PITFALLS.md confirms that store_db.py own comments require a schema version bump for any structural column addition. Using gate_detail_json violates the module documented convention and creates silent schema_version inconsistency.
4. **The migration risk is low.** Six prior schema migrations have executed without incident. Two nullable ALTER TABLE ADD COLUMN DEFAULT NULL statements carry negligible risk.
5. **gate_detail_json defeats the purpose.** If industry momentum never leaves the JSON blob, the winner/loser analysis cannot include it as a discriminating variable -- which is the milestone core hypothesis.

---

## Key Findings

### Recommended Stack

The entire implementation reuses existing infrastructure. yfinance 0.2.x already returns info[industryKey] at no extra API cost -- _make_quality_info() already calls yf.Ticker(ticker).info per ticker, so adding industry fields is zero-cost. The momentum calculation follows the _sector_strength() pattern: pandas 20-day rate-of-change on ETF price DataFrames already loaded into the market_data dict.

A curated INDUSTRY_ETF_MAP of approximately 20 liquid SPDR/iShares sub-sector ETFs covers the most common SP400/500/600 industries (XSD for semiconductors, XBI for biotech, KRE for regional banks, XOP for E&P energy, XRT for retail, XHB for homebuilders) with a two-tier fallback to SECTOR_ETF_MAP for unmapped industries.

**Core technologies:**
- yfinance 0.2.x (already installed): industryKey classification -- zero additional network calls per ticker
- pandas (already installed): 20-day ROC and SMA50 on ETF frames -- identical computation pattern to _sector_strength()
- Parquet ETF cache via data_store.get_market_data(): extend _MARKET_SYMBOLS with ~10 industry ETF tickers -- zero structural change to the cache layer
- scipy.stats (optional): Mann-Whitney U for W/L significance testing -- skip for v1; pandas percentile comparisons are sufficient

### Expected Features

**Must have (table stakes, v1):**
- Industry group name stored on every signal -- root enabling field; all other features depend on it
- Industry 20-day momentum score (ETF ROC vs SPY) stored on signal
- Top-half flag (boolean) derived from RS ranking across universe
- Industry momentum direction (Improving / Neutral / Declining) from dual-window comparison
- Schema v7 migration: industry TEXT, industry_momentum REAL as nullable columns on signals
- Per-metric bucket tables in backtest report for pullback discriminators (RSI, vol_contraction, pullback_depth_pct, rs_strength) and breakout discriminators (vol_ratio, ADX, pct_to_52w_high)
- Median winner vs loser comparison table in report.md

**Should have (after v1 backtest data collected):**
- Industry rank absolute position (1 of N)
- Rank delta vs 4 weeks prior -- requires two scan dates of history
- Industry momentum as W/L discriminating variable in bucket analysis

**Defer (v2+):**
- Score component contribution analysis -- high complexity; defer until W/L analysis confirms a useful signal
- Cross-metric interaction effects (RSI x vol_contraction combined) -- needs 750+ qualified trades minimum
- UI display of industry fields in Angular candidates page -- validate in CLI/report first

### Architecture Approach

The implementation has a clean six-phase dependency chain: (1) data layer -- add ETF symbols and QualityInfo.industry field; (2) _industry_momentum() helper in core.py; (3) signal pipeline wiring in run_scan() and generate_signals(); (4) DB schema v7 migration; (5) API + Angular display; (6) winner/loser analysis in report.py. The chain groups into two delivery phases: industry display on signals (1-5) and winner/loser analysis in backtest report (6).

**Major components touched:**
1. core.py -- add INDUSTRY_ETF_MAP, QualityInfo.industry field, _industry_momentum() helper, post-evaluation wiring in run_scan()
2. data_store.py -- extend _MARKET_SYMBOLS with ~10 industry ETF tickers
3. store_db.py -- schema v7 migration (two ALTER TABLE ADD COLUMN statements)
4. simulate.py + backtest.py -- Signal/Trade dataclass fields; backtest loop wiring
5. report.py -- winner_loser_analysis() function; render_report() integration
6. web/api/routes/runs.js + Angular UI -- unpack winner_loser_analysis from metrics_json; TypeScript interface updates

**Critical architectural constraint:** Do NOT add industry_momentum to EvalContext. It is a post-evaluation display field, not a gate input. Compute it in the same post-eval block as ath_zone and confidence. Adding it to EvalContext invites accidental gate use before backtest evidence exists.

### Critical Pitfalls

1. **Look-ahead bias in backtest ETF momentum** -- Industry ETF prices must be accessed only through sliced_market[etf_symbol] (already filtered to df.index <= as_of_ts in backtest.py line 314). Never call get_history() inside the date-by-ticker inner loop. Required UAT: spot-check that the ETF price used at signal date T equals the historical close on date T.

2. **Overfitting via multiple comparisons in W/L analysis** -- Pre-register the features to be tested before running analysis. This is the exact failure mode behind the ADX and volume-contraction gate reversals. MIN_BUCKET_N = 20 is insufficient for subgroup analysis -- use 50 minimum per cell.

3. **Insufficient sample size for subgroup analysis** -- A 2-year SP500 backtest produces ~150-400 qualified trades. Analysis must abort with an explicit message if qualified trade count < 200; cells with n < 50 must be suppressed.

4. **Sector reclassification bias** -- yf.Ticker().info[industry] returns today classification, not the historical one. Treat as a display annotation. Add to the biases list in backtest report JSON output alongside _BIAS_LOOK_AHEAD.

5. **Silent None/zero substitution** -- Use Optional[float] throughout the pipeline. Never coerce missing momentum to 0.0 -- zero looks like neutral in the UI but means no data. Test: tickers with no sector tag must produce NULL in DB, not 0.0.

---

## Implications for Roadmap

### Phase 1: Data Foundation + Industry Classification
**Rationale:** Everything depends on industry classification being in QualityInfo and industry ETF prices being in the market data cache. Pure plumbing with no user-visible output; testable in isolation.
**Delivers:** QualityInfo.industry populated; INDUSTRY_ETF_MAP defined; ~10 industry ETF tickers in _MARKET_SYMBOLS and Parquet-cached
**Addresses:** Root dependency (industry group name); STACK.md ETF map and QualityInfo extension
**Avoids:** Performance trap of fetching yf.Ticker().info inside the backtest inner loop -- must cache at startup
**Research flag:** Standard patterns -- no deeper research needed

### Phase 2: Industry Momentum Computation + Schema v7 + Signal Pipeline
**Rationale:** With Phase 1 complete, _industry_momentum() can be implemented and wired into both scan and backtest loops. Schema v7 migration ships here so values are persisted immediately.
**Delivers:** industry_mom_20d, industry_above_50ma, industry_rs_spy computed per signal; schema v7 live; top-half flag and direction label stored on signal
**Addresses:** All P1 table-stakes features from FEATURES.md; schema v7 migration
**Avoids:** Look-ahead bias (must anchor to as_of); must NOT add to EvalContext; must follow ath_zone post-eval pattern exactly
**Research flag:** Highest execution risk phase -- the as_of anchoring is the critical correctness step; backtest spot-check test is a required UAT item before phase close

### Phase 3: API + UI Display
**Rationale:** With signals containing industry fields in the DB, the web layer surfaces them. Express requires no route changes (SELECT * handles it).
**Delivers:** Industry group name and momentum indicator visible in Angular candidates page; TypeScript Signal interface updated
**Avoids:** None/zero display bug -- UI must render dash, not 0.0, for null momentum fields
**Research flag:** Standard patterns -- Angular nullable field display already handled in the existing signal table

### Phase 4: Winner/Loser Characteristic Analysis
**Rationale:** Must come after Phase 2 (requires industry_momentum on Signal/Trade). Additive to report.py -- does not change any existing gate or scoring logic.
**Delivers:** winner_loser_analysis() in report.py; per-metric bucket tables for pullback and breakout discriminators; median W/L comparison table; winner_loser_analysis section in Express /api/runs/:run_id; Angular backtests page display
**Addresses:** All W/L table-stakes features; differentiators (median comparison table, min sample size guard)
**Avoids:** Multiple comparisons overfitting -- feature list MUST be pre-registered in the phase spec before any backtest run; correlation trap -- Spearman(industry_momentum, rs_strength) computed and disclosed; insufficient sample size -- aborts if qualified trades < 200, cells with n < 50 suppressed
**Research flag:** Highest analysis risk phase -- the phase design doc must specify which features are tested, the notable threshold, and required n per cell BEFORE any results are viewed. This pre-registration is the guard against the ADX/volume-contraction failure mode.

### Phase Ordering Rationale

- Phase 1 before Phase 2: Hard technical dependency -- cannot compute momentum without ETF map and QualityInfo.industry
- Phase 2 before Phase 3: Schema v7 must exist before the web layer displays the fields
- Phase 2 before Phase 4: W/L analysis requires industry_momentum on Trade objects, which requires Signal pipeline wiring
- Phases 3 and 4 can be parallelised -- they touch different layers (web vs Python report) with no shared implementation dependencies
- W/L analysis is intentionally last -- industry_momentum must be stored on historical signals before the analysis is meaningful

### Research Flags

Phases needing extra attention during execution:
- **Phase 2:** as_of anchoring for ETF price lookups is the highest-risk implementation step; backtest spot-check test must be in UAT criteria
- **Phase 4:** Pre-registration of features to test must happen in the phase plan before any results are viewed; minimum sample size check is a hard gate, not an advisory

Phases with standard patterns (lower execution risk):
- **Phase 1:** Adding dict entries and a dataclass field -- established pattern
- **Phase 3:** TypeScript interface extension and Angular nullable field display -- established pattern

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | yfinance industryKey confirmed via context7; ETF proxy map cross-checked but not live-validated against yfinance industry name strings |
| Features | MEDIUM | IBD RS methodology from community sources; TraderAssist codebase direct inspection is HIGH confidence |
| Architecture | HIGH | Based entirely on direct codebase reading; all six integration layers confirmed; ath_zone as exact precedent is reliable |
| Pitfalls | HIGH | Look-ahead bias and multiple comparisons pitfalls cross-verified against codebase patterns and statistical literature |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **yfinance industry name string validation:** The industry name strings that yfinance returns must be empirically validated against live tickers before INDUSTRY_ETF_MAP can be relied upon. Phase 1 UAT: fetch .info[industry] for 10 representative tickers per sector and confirm strings match the map keys.
- **ETF inception dates for pre-2023 backtests:** SPDR sub-sector ETFs have varying inception dates. Document the specific ETFs that lack pre-2015 history alongside inception dates in the map; the sector-ETF fallback handles this at runtime.
- **Industry momentum lookback parameter:** STACK.md recommends 20 days aligned with the 5-20 day hold window. Treat as a hypothesis, not a hardcoded constant. Document visibly in the phase plan so it can be revisited after the first W/L backtest run.

---

## Sources

### Primary (HIGH confidence)
- D:/Projects/TraderAssist/scanner/ -- direct codebase inspection: core.py, backtest.py, simulate.py, report.py, store_db.py, data_store.py
- D:/Projects/TraderAssist/.planning/PROJECT.md -- constraints, ADX/volume-contraction reversal history
- D:/Projects/TraderAssist/CLAUDE.md -- schema v6 current state, key design decisions table

### Secondary (MEDIUM confidence)
- /websites/ranaroussi_github_io_yfinance (context7) -- Ticker.info field reference, industryKey confirmed
- yfinance const.py (context7) -- complete industry key taxonomy (~118 slugs)
- yfinance GitHub issue #1471 -- info sector/industry field name changes between versions
- IBD/MarketSmith industry group ranking methodology (websearch) -- RS display format, top-half threshold
- Statistical significance in backtesting, multiple comparisons bias (medium.com, QuantRocket, Bailey et al.)

### Tertiary (LOW confidence)
- SPDR S&P Select Industry ETF ticker list (websearch) -- cross-checked against known liquid ETFs but not validated via live yfinance download
- 20-day lookback for swing trading momentum (practitioner sources) -- reasonable but not empirically validated against this dataset

---
*Research completed: 2026-06-30*
*Ready for roadmap: yes*
