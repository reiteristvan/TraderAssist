# Pitfalls Research

**Domain:** Industry/sector momentum display field + winner/loser characteristic analysis for a Python swing trading scanner
**Researched:** 2026-06-30
**Confidence:** HIGH (critical pitfalls cross-verified against codebase; sample-size thresholds from statistical literature; yfinance behavior from official docs and known issues)

---

## Critical Pitfalls

### Pitfall 1: Look-ahead bias in industry ETF momentum during backtesting

**What goes wrong:**
The backtest fetches or computes industry ETF momentum using a rolling window that is not anchored to `ctx.as_of`. The ETF's current price (or a recent slice that extends past `as_of`) bleeds into the computation, making the momentum signal stronger or more directionally aligned than it would have been at signal time. The backtest win/loss split then shows industry momentum as "predictive" — but only because it had access to future price information.

**Why it happens:**
The display field works correctly in live scanning (there is no future to leak). Developers add the live-scan code first, test it, see it working, then reuse the same logic in the backtest loop without realising the frame is not already sliced. The existing `_precompute_bars` / `.asof(as_of_ts)` pattern protects against this for per-ticker indicators but is not automatically applied to market-context data (ETF prices) unless the developer deliberately extends the pre-loading step.

**How to avoid:**
Industry ETF OHLCV data must be loaded into `full_market` (the same dict that already holds `SPY`, `QQQ`, etc.) via `get_market_data()` before the backtest date loop begins. Inside the loop, ETF prices must be accessed only through `sliced_market[etf_symbol]`, which is already filtered to `df.index <= as_of_ts` on line 314 of `backtest.py`. Never call `get_history(etf_symbol)` inside the loop. Follow the exact same pattern used for `rs_strength` vs SPY.

**Warning signs:**
- Industry momentum shows unusually high predictive power (>10 percentage-point win-rate difference across momentum buckets) in the backtest but cannot be reproduced in live forward testing.
- ETF momentum values in the backtest output are identical to values computed in a live scan for the same ticker on the same date.
- The momentum calculation touches `pd.Timestamp.today()` or uses an unsliced DataFrame anywhere in the code path called from `generate_signals`.

**Phase to address:**
Phase computing industry ETF momentum. Add an explicit test: assert that the ETF price used in momentum calculation at signal date T equals the ETF's historical close on date T, not any later date. The `_bars_loader` and `_market_loader` test seams in `generate_signals` are the right injection points for verifying this.

---

### Pitfall 2: Sector reclassification bias — yfinance tags are point-in-time snapshots of today

**What goes wrong:**
`yf.Ticker(ticker).info['sector']` and `info['industry']` return the ticker's **current** classification as of today, not its classification at the historical signal date. GICS reorganised in 2018 (communications services was carved out of telecom plus parts of technology and consumer discretionary). Stocks that moved sectors during the backtest period are evaluated against ETFs they were not in at signal time. The `_BIAS_LOOK_AHEAD` note in `report.py` already acknowledges this for fundamentals fields — the industry tag amplifies the problem because it drives *which ETF prices* are used, turning a labeling error into a structural data error.

**Why it happens:**
yfinance's `.info` dict is a scrape of the current Yahoo Finance profile page. There is no historical point-in-time sector/industry feed available through yfinance. Developers assume the classification is stable because most large-cap names are stable — but edge cases (spin-offs, GICS realignments, class-action delisting) are common enough across SP400/500/600 universes to bias results.

**How to avoid:**
Treat the sector/industry tag as a *display annotation* derived at scan time (today's classification), not as a historical fact reconstructed during backtesting. Do not allow the industry tag to change the ETF used for momentum in a backtest — use a single fixed ETF-per-sector mapping (the `SECTOR_ETF_MAP` already in `core.py` is appropriate) keyed on the ticker's current sector. Accept this as a known bias and add it to the `biases` list in `report.py`'s JSON output alongside the existing `_BIAS_LOOK_AHEAD` string. Do not attempt to reconstruct historical sector assignments from yfinance.

**Warning signs:**
- A sector in the backtest universe has an unusually high rate of `None` industry momentum values (likely a ticker whose current sector has no ETF mapping).
- Tickers that are known spin-offs or recent IPOs (post-2020) show industry momentum inconsistent with their current sector's ETF trajectory.

**Phase to address:**
Phase adding industry momentum as a display field. Document the classification-staleness bias explicitly in the phase's UAT criteria and in `report.py`'s bias section.

---

### Pitfall 3: Correlation trap — industry momentum is a noisy proxy for the existing RS gate

**What goes wrong:**
The scanner already computes `rs_strength = (stock/spy) / (stock/spy).shift(60)` for each ticker. Industry ETF momentum is essentially `etf_price / etf_price.shift(N)` where `etf_price` is the aggregate of stocks in the same sector. These two quantities are structurally correlated: when a sector outperforms SPY, both the stocks in it and the sector ETF post positive momentum. In the winner/loser analysis, industry momentum may appear to be a strong discriminating feature — but the effect may entirely come from the existing RS gate co-varying with it. The apparent "new insight" is a re-measurement of something the scanner already captures.

**Why it happens:**
Correlation between features is invisible in a univariate comparison table. Displaying "winners had higher industry momentum" is true but misleading if winners also had higher RS, and RS already gates out weak-RS stocks. The partial effect of industry momentum (holding RS constant) may be near zero.

**How to avoid:**
In the winner/loser analysis, compare industry momentum distributions *within RS bands* — e.g., "among trades where RS was 0.90–1.05, do winners still show higher industry momentum than losers?" Only if the signal holds within RS-controlled subgroups does it carry independent predictive value. Do not present a top-level winner/loser split by industry momentum as evidence for gate candidacy without this control step.

**Warning signs:**
- Pearson or Spearman correlation between `rs_strength` and the industry ETF momentum value at the same signal date is above 0.6.
- When sorted by industry momentum, the winner/loser split disappears or inverts in RS-controlled cohorts.

**Phase to address:**
Phase adding winner/loser characteristic analysis. The analysis logic must include a correlation check between all displayed features and the existing scored/gated features before surfacing any "discriminating" finding to the owner.

---

### Pitfall 4: Overfitting via multiple comparisons in winner/loser analysis

**What goes wrong:**
The winner/loser analysis compares 8–15 entry-time features (RSI level, ATR multiple, industry momentum, ADX, score bucket, confidence tier, distance from MA200, days to earnings, volume ratio, etc.) between winners and losers. With N=300 backtest trades and 12 features, roughly 1–2 features will appear statistically significant at p<0.05 purely by chance, even if no feature has real predictive value. The first feature that "looks significant" gets proposed as a gate candidate. The gate is added. Forward performance degrades. This is the exact failure mode that already caused the ADX and volume contraction gate reversals.

**Why it happens:**
It is easy to iterate feature comparisons in a loop and sort by the one with the biggest apparent difference. The PROJECT.md explicitly warns against this pattern, but the machinery of a winner/loser table makes it easy to fall into accidentally, especially when results are presented as a ranked table.

**How to avoid:**
Pre-register the features and hypotheses before running the analysis — commit the list of features to be tested before looking at the results. Apply Bonferroni correction or Benjamini-Hochberg FDR control when testing multiple features on the same dataset. Treat any apparent discriminating feature as hypothesis-generating only, requiring an independent forward test on a held-out date range before gate candidacy. The `MIN_BUCKET_N = 20` threshold in `report.py` is insufficient for subgroup analysis — use a minimum of 50 trades per subgroup cell (winner with high momentum, loser with high momentum, etc.) before drawing conclusions.

**Warning signs:**
- The first version of the winner/loser table has more than one feature showing a "notable" difference (>5 percentage points in win rate) without a prior hypothesis.
- Any feature produces a win-rate difference larger than 15 percentage points with fewer than 100 trades in each subgroup.
- Results change meaningfully (>5 points) when the backtest date range is shifted by 3 months.

**Phase to address:**
Phase adding winner/loser characteristic analysis. The design must specify which features are tested (committed up front), what threshold constitutes "notable", and what sample size is required per cell before a finding is surfaced.

---

### Pitfall 5: Insufficient sample size — the winner/loser split degrades statistical power at subgroup level

**What goes wrong:**
A 2-year backtest over SP500 with the current gate setup produces roughly 150–400 qualified trades (the scanner's ~50% stop rate means half are losers). When split into winner vs loser by any single feature with 4 buckets, each cell has 20–50 trades — below the 100-trade threshold for reliable performance metrics (López de Prado / standard practice). Results will fluctuate by 10–15 percentage points between backtest runs covering slightly different date ranges, creating false confidence in findings that are purely sampling noise.

**Why it happens:**
The analysis is conceived at the whole-portfolio level (300+ trades looks like a large sample) without accounting for the cell sizes after partitioning. The existing `MIN_BUCKET_N = 20` in `report.py` was calibrated for the score-bucket analysis (all qualified trades in one bucket) and is not appropriate when further subdividing by a second dimension.

**How to avoid:**
For a 2-dimensional split (winner/loser × feature bucket), require a minimum of 50 trades *in each cell* before reporting a win-rate. For a 3-dimensional split (winner/loser × feature bucket × market regime), the requirement is ~80–100 per cell — achievable only with 3+ years of history covering at least two market regimes. Size the backtest date range to yield the required cell counts before interpreting results, not after. Report cell sizes prominently alongside win rates. Collapse buckets when counts are insufficient rather than reporting low-n results as "inconclusive".

**Warning signs:**
- Total qualified trades in the backtest run are below 200.
- Any analysis cell (winner + feature bucket combination) has fewer than 30 trades.
- The same backtest run over a 3-month offset in start date produces win-rate differences >10 points in the same bucket.

**Phase to address:**
Phase adding winner/loser characteristic analysis. The phase spec must include a "minimum backtest sample" prerequisite check that aborts the analysis with an explicit message if qualified trade counts are insufficient.

---

## Moderate Pitfalls

### Pitfall 6: ETF inception date gap — history shorter than the backtest range

**What goes wrong:**
If the project moves beyond the 11 SPDR sector ETFs (already in `SECTOR_ETF_MAP`) to granular industry group ETFs (the stated goal in PROJECT.md), many of those ETFs launched after 2015. A backtest starting in 2023 is probably safe, but a backtest extending to 2020 or earlier will have missing ETF history for some industry groups. yfinance returns `None` or an empty DataFrame silently — the scanner must not mistake "ETF has no history" for "industry has zero momentum."

**How to avoid:**
Add an ETF inception date check when loading industry ETF data: verify the ETF has at least `lookback + 30` trading days of history before `as_of`. Fall back to the parent sector ETF (already in `SECTOR_ETF_MAP`) if the industry ETF history is insufficient. Log the fallback. Never substitute `0.0` for a missing momentum value; use `None` and surface it as "N/A" in the display field.

**Warning signs:**
- Industry momentum is `None` for all signals in a specific industry group during early backtest periods.
- An ETF in the mapping was listed after 2015 but is being used in a backtest starting earlier.

**Phase to address:**
Phase computing industry ETF momentum.

---

### Pitfall 7: Momentum lookback period mismatch with hold duration

**What goes wrong:**
Using a 60-day momentum lookback for an industry ETF (matching the existing `RS_LOOKBACK = 60` for individual stocks) on a strategy with a 5–15 day hold period creates a phase mismatch: the momentum signal captures what happened 2 months ago, not the current directional regime. A sector can be in a 60-day uptrend but a 5-day reversal — the backtest signal fires into the reversal. Conversely, using a 5-day lookback captures noise rather than trend.

**How to avoid:**
Use a lookback of 20–30 days for industry ETF momentum when the strategy hold period is 5–15 days. This aligns the momentum measurement horizon with the trade duration. Present the lookback parameter prominently in the display field label (e.g., "Ind. Mom (20d)"). Do not silently reuse `RS_LOOKBACK` without verifying it makes sense for the hold period.

**Warning signs:**
- Industry ETF momentum values are frequently opposite in sign to the individual stock's price action during the same period.
- Short-term sector reversals are common but the momentum field consistently shows the prior trend.

**Phase to address:**
Phase computing industry ETF momentum (parameter selection step).

---

### Pitfall 8: Silent None / zero substitution corrupts the display field

**What goes wrong:**
When yfinance fails to return sector data for a ticker (new IPOs, ETFs themselves, foreign listings, special share classes), the code substitutes `0.0` for the missing momentum value. Zero is interpreted as "neutral momentum" in the UI, but it actually means "no data." The owner may make a trading decision based on a false "neutral" reading. This is especially insidious for breakout signals where the underlying stock may have excellent sector tailwinds that simply weren't fetched.

**How to avoid:**
Use `Optional[float]` for the industry momentum field throughout the pipeline (signal dataclass, DB column, API response, UI display). Display `—` or `N/A` in the UI when the value is null — never coerce to zero or any sentinel numeric value. Add a test that verifies a missing sector tag produces a `None` momentum value at the signal level, not a zero.

**Warning signs:**
- Industry momentum shows exactly `0.0` for any signal (0.0 is not a natural rate-of-change value; true neutral is ~1.0 for ratio-based RS or ~0.0% for percentage-change).
- Signals for tickers where `yf.Ticker(t).info.get('sector')` returns `None` still show a momentum value.

**Phase to address:**
Phase adding industry momentum as a display field.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reuse `RS_LOOKBACK = 60` for industry ETF momentum without validation | No new parameter to tune | Lookback mismatch with hold period produces misleading momentum values in display | Never — validate the lookback against hold duration before hardcoding |
| Map `None` sector tag to neutral/zero momentum | Avoids null handling in the pipeline | Owner unknowingly acts on false "neutral" signals | Never — always surface as N/A |
| Add industry momentum column to DB without schema version bump | Faster to ship | Breaks schema_version checks; existing DB files become inconsistent | Never — `store_db.py` comment explicitly requires version bump for new columns |
| Compute industry ETF momentum inline at query time (lazy, per-scan) | Simple implementation | Look-ahead bias in backtest mode if not carefully gated by `as_of` | Only if backtest path is explicitly excluded and a code comment blocks future backtest use |
| Accept yfinance sector tag as historical fact in backtest | Simpler than acknowledging the bias | Sector misclassification for stocks that changed sectors inflates apparent momentum correlation | Only during display-only phase; must be disclosed in bias section and not used as gate evidence |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| yfinance `Ticker.info` for sector/industry | Calling it inside the backtest date loop (one call per ticker×day) causes rate limiting and returns today's classification at every date | Call once per ticker at startup, outside the loop; cache the result in `quality_by_ticker` alongside the existing `QualityInfo` fields |
| yfinance ETF OHLCV history | Fetching ETF bars in a separate `get_history()` call path that bypasses the Parquet cache | Add industry ETFs to `get_market_data()` so they share the same Parquet caching and rate-limit protection as SPY/QQQ |
| yfinance version drift (`info` fields) | Field name `industry` vs `industryKey` — broke between versions 0.2.12 and 0.2.14 (documented GitHub issue #1471) | Always use `.get('industryKey') or .get('industry')` with a fallback; add a version-guard test |
| DB schema | Adding `industry_momentum` to `signals` table without bumping `schema_version` | Follow the existing schema bump pattern in `store_db.py`; current version is 6, bump to 7 |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching industry ETF history inside the backtest per-ticker×day inner loop | Backtest runtime goes from minutes to hours; rate limit errors from yfinance | Pre-load all required ETF history into `full_market` before the outer date loop, following the existing `_market_loader` pattern | Immediately, on first backtest run with the naive implementation |
| Calling `yf.Ticker(t).info` per ticker inside `generate_signals` | Network calls inside the tight loop; batch of 500 SP500 tickers triggers 429 rate limiting | Cache sector/industry in `QualityInfo` or a separate dict loaded once at startup | At 50+ tickers in the universe |
| Running winner/loser analysis on every `render_report` call | Acceptable at 200 trades; slow at 2000 trades if analysis requires sorting and bucketing across all features | Gate the analysis behind a minimum trade count check; make it an opt-in flag rather than always-on in `render_report` | At 1000+ trades, measurable report generation slowdown |

---

## "Looks Done But Isn't" Checklist

- [ ] **Industry momentum display field:** Verify that the ETF price used in the backtest at signal date T is the ETF's historical close on date T, not today's price. Run a spot-check: pick a signal from 90 days ago and confirm the momentum value matches what you would have seen in a live scan on that date.
- [ ] **Sector tag caching:** Verify that `yf.Ticker().info` is called at most once per ticker per scan run, not once per signal or inside a loop.
- [ ] **None handling:** Verify that tickers with no sector tag produce a `None` momentum value in the DB column, not `0.0`. Query `SELECT ticker, industry_momentum FROM signals WHERE industry_momentum = 0.0 LIMIT 10` and confirm those tickers all have valid sectors.
- [ ] **Schema version:** Verify `SELECT version FROM schema_version` returns the expected incremented value after migration.
- [ ] **Winner/loser analysis cell sizes:** Verify the analysis reports cell counts (n) prominently alongside win rates and suppresses results where n < 50.
- [ ] **Bias disclosure:** Verify the industry momentum classification-staleness bias appears in the backtest report's bias section, not just in code comments.
- [ ] **Correlation check:** Before presenting industry momentum as a gate candidate, verify Spearman correlation between `industry_momentum` and `rs_strength` is computed and shown; if rho > 0.6, the analysis notes the redundancy explicitly.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Look-ahead bias discovered post-implementation | HIGH | Re-run all backtests that included industry momentum in the winner/loser analysis; discard any gate candidacy conclusions drawn from tainted results; fix the data slicing before re-analysing |
| Sector tag misclassification discovered in DB | MEDIUM | Add migration to set `industry_momentum = NULL` for known reclassified tickers; re-scan those tickers; add bias note to existing backtest reports |
| Schema version not bumped, DB inconsistency | MEDIUM | Write a migration script following the existing `store_db.py` pattern; add a test that verifies schema version matches expected after each migration |
| Multiple comparison overfitting — gate added based on spurious winner/loser finding | HIGH | Revert the gate (same process as the ADX and volume-contraction reversals); run a new backtest without the gate; update the post-mortem entry in PROJECT.md |
| ETF inception date gap silently produces wrong results | LOW | Add inception date validation on startup; log a warning; fall back to parent sector ETF; re-scan affected date ranges |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Look-ahead bias in ETF momentum (Pitfall 1) | Phase: industry ETF momentum computation | Backtest spot-check: momentum value at date T matches historical ETF close on date T |
| Sector reclassification / tag staleness (Pitfall 2) | Phase: industry ETF momentum display field | Bias disclosure present in backtest report JSON; acknowledged in phase UAT |
| Correlation trap with existing RS gate (Pitfall 3) | Phase: winner/loser characteristic analysis | Spearman(industry_momentum, rs_strength) computed and disclosed before any gate candidacy claim |
| Overfitting via multiple comparisons (Pitfall 4) | Phase: winner/loser characteristic analysis | Feature list pre-registered; Bonferroni-corrected p-values or explicit "hypothesis-generating only" label on output |
| Insufficient sample size for subgroup analysis (Pitfall 5) | Phase: winner/loser characteristic analysis | Phase spec includes minimum qualified-trade prerequisite; analysis aborts with clear message if not met |
| ETF inception date gap (Pitfall 6) | Phase: industry ETF momentum computation | ETF history length validated before use; fallback to sector ETF logged |
| Lookback period mismatch (Pitfall 7) | Phase: industry ETF momentum computation (parameter selection) | Lookback explicitly chosen vs hold duration; documented in phase plan |
| Silent None / zero substitution (Pitfall 8) | Phase: industry ETF momentum display field | Test: tickers with no sector produce NULL in DB, not 0.0; UI shows N/A |

---

## Sources

- yfinance official docs, Sector and Industry module: https://ranaroussi.github.io/yfinance/reference/yfinance.sector_industry.html
- yfinance GitHub issue #1471 — `info` sector/industry fields broke between v0.2.12 and v0.2.14: https://github.com/ranaroussi/yfinance/issues/1471
- Statistical significance in backtesting (medium.com/@trading.dude): https://medium.com/@trading.dude/how-many-trades-are-enough-a-guide-to-statistical-significance-in-backtesting-093c2eac6f05
- Multiple comparisons / p-hacking in quantitative finance (QuantRocket): https://www.quantrocket.com/codeload/quant-finance-lectures/quant_finance_lectures/Lecture23-p-Hacking-and-Multiple-Comparisons-Bias.ipynb.html
- Pseudo-Mathematics and Financial Charlatanism — Bailey et al. (backtest overfitting): https://www.researchgate.net/publication/275302374_Pseudo-Mathematics_and_Financial_Charlatanism_The_Effects_of_Backtest_Overfitting_on_Out-of-Sample_Performance
- RS calculation mistakes and RS vs RSI confusion (StockCharts ChartSchool): https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/price-relative-relative-strength
- Implementation risk in portfolio backtesting (sector classification): https://arxiv.org/html/2603.20319
- TraderAssist codebase — `scanner/backtest.py`, `scanner/report.py`, `scanner/core.py`, `CLAUDE.md`

---
*Pitfalls research for: Industry/sector momentum + winner/loser analysis — TraderAssist swing scanner*
*Researched: 2026-06-30*
