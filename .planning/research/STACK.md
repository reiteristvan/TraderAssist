# Stack Research

**Domain:** Python swing trading scanner — industry/sector momentum extension
**Researched:** 2026-06-30
**Confidence:** MEDIUM (yfinance API verified via context7; ETF proxy map cross-checked via web sources; momentum calculation practices from community sources, LOW confidence)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| yfinance | 0.2.x (already installed) | Industry/sector classification via `info['industryKey']` | Already used in `_make_quality_info()`; `info` dict returns `industryKey` and `sectorKey` at no extra API cost since it is fetched per-ticker anyway |
| pandas | already installed | 20-day ROC, SMA50 calculation on ETF price series | Same pattern as existing `_sector_strength()` in `core.py` |
| yfinance download / Parquet cache | same | Industry ETF price history for momentum calculation | Extend `get_market_data()` to include industry ETFs alongside existing sector ETFs; reuses the existing Parquet caching layer |
| scipy.stats (optional) | ~1.11 | Mann-Whitney U test for winner/loser discriminant analysis | Only needed if statistical significance testing is added; pandas percentile comparisons work for display-only analysis |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy.stats | ~1.11 | Rank-sum test between winners and losers | Only needed for winner vs loser phase; skip for display-only industry momentum phase |
| ta (already installed) | already used | Not needed for industry momentum | Existing usage for MACD in confidence scoring; no new ta usage needed |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Existing test suite | All Python changes must keep `pytest -q` green; test with mocked `market_data` dict |
| yfinance sandbox / mock | Unit testing | Monkeypatch `_make_quality_info` for industry tests same as existing quality tests |

---

## Data Classification: How to Get `industryKey`

**The field already exists in every `.info` fetch.** `yf.Ticker(ticker).info` returns:

```python
{
  "sector":      "Technology",                # human-readable, already in QualityInfo
  "sectorKey":   "technology",                # slug, not yet stored
  "industry":    "Software—Infrastructure",  # human-readable
  "industryKey": "software-infrastructure",  # slug — use this as map key
  ...
}
```

`_make_quality_info()` in `core.py` already calls `yf.Ticker(ticker).info`. **No additional API call is needed.** Add `industry_key: Optional[str]` to `QualityInfo` and store `info.get('industryKey')`.

**Full industry key taxonomy (from yfinance const.py, confirmed via context7):** 11 sectors, ~118 industries. Key industry slugs:

| Sector | Example industryKey values |
|--------|---------------------------|
| Technology | `semiconductors`, `software-infrastructure`, `software-application`, `consumer-electronics`, `communication-equipment` |
| Healthcare | `biotechnology`, `drug-manufacturers-general`, `medical-devices`, `healthcare-plans`, `diagnostics-research` |
| Financial Services | `banks-regional`, `banks-diversified`, `capital-markets`, `insurance-property-casualty`, `insurance-life` |
| Consumer Cyclical | `residential-construction`, `specialty-retail`, `internet-retail`, `auto-manufacturers`, `restaurants` |
| Industrials | `aerospace-defense`, `airlines`, `specialty-industrial-machinery`, `engineering-construction`, `railroads` |
| Energy | `oil-gas-e-p`, `oil-gas-equipment-services`, `oil-gas-integrated`, `oil-gas-midstream` |
| Basic Materials | `gold`, `specialty-chemicals`, `steel`, `copper`, `aluminum` |
| Real Estate | `reit-retail`, `reit-industrial`, `reit-office`, `reit-residential` |

---

## Industry ETF Proxy Map

### Strategy

1. **Primary:** industry-level ETF — SPDR S&P Select Industry or iShares sub-sector ETF
2. **Fallback:** existing `SECTOR_ETF_MAP` entry for the stock's sector
3. **If neither:** skip (`None`) — do not fail the evaluation

This two-tier design means every qualified signal gets _some_ momentum reading (worst case: sector-level), and the ~20 liquid industry ETFs provide finer discrimination where available.

### Recommended `INDUSTRY_ETF_MAP` (industryKey → ETF ticker)

All tickers below are confirmed tradeable on US exchanges and accessible via `yf.download()`.

**Technology**
| industryKey | ETF | Name |
|------------|-----|------|
| `semiconductors` | XSD | SPDR S&P Semiconductor ETF |
| `semiconductor-equipment-materials` | XSD | SPDR S&P Semiconductor ETF |
| `software-infrastructure` | XSW | SPDR S&P Software & Services ETF |
| `software-application` | XSW | SPDR S&P Software & Services ETF |
| `information-technology-services` | XSW | SPDR S&P Software & Services ETF |

**Healthcare**
| industryKey | ETF | Name |
|------------|-----|------|
| `biotechnology` | XBI | SPDR S&P Biotech ETF (equal-weight; more volatile than IBB but broader) |
| `drug-manufacturers-general` | XPH | SPDR S&P Pharmaceuticals ETF |
| `drug-manufacturers-specialty-generic` | XPH | SPDR S&P Pharmaceuticals ETF |
| `medical-devices` | XHE | SPDR S&P Health Care Equipment ETF |
| `medical-instruments-supplies` | XHE | SPDR S&P Health Care Equipment ETF |
| `healthcare-plans` | XHS | SPDR S&P Health Care Services ETF |
| `medical-care-facilities` | XHS | SPDR S&P Health Care Services ETF |

**Financial Services**
| industryKey | ETF | Name |
|------------|-----|------|
| `banks-regional` | KRE | SPDR S&P Regional Banking ETF |
| `banks-diversified` | KBE | SPDR S&P Bank ETF |
| `insurance-property-casualty` | KIE | SPDR S&P Insurance ETF |
| `insurance-life` | KIE | SPDR S&P Insurance ETF |
| `insurance-diversified` | KIE | SPDR S&P Insurance ETF |
| `capital-markets` | KCE | SPDR S&P Capital Markets ETF |
| `financial-data-stock-exchanges` | KCE | SPDR S&P Capital Markets ETF |

**Consumer Cyclical**
| industryKey | ETF | Name |
|------------|-----|------|
| `residential-construction` | XHB | SPDR S&P Homebuilders ETF |
| `specialty-retail` | XRT | SPDR S&P Retail ETF |
| `department-stores` | XRT | SPDR S&P Retail ETF |
| `internet-retail` | XRT | SPDR S&P Retail ETF |

**Industrials**
| industryKey | ETF | Name |
|------------|-----|------|
| `aerospace-defense` | XAR | SPDR S&P Aerospace & Defense ETF |

**Energy**
| industryKey | ETF | Name |
|------------|-----|------|
| `oil-gas-e-p` | XOP | SPDR S&P Oil & Gas E&P ETF |
| `oil-gas-integrated` | XLE | (sector ETF fallback — no dedicated sub-sector ETF) |
| `oil-gas-equipment-services` | XES | SPDR S&P Oil & Gas Equipment & Services ETF |
| `oil-gas-midstream` | XLE | (sector ETF fallback) |

**Basic Materials**
| industryKey | ETF | Name |
|------------|-----|------|
| `gold` | GDX | VanEck Gold Miners ETF (not SPDR but de-facto standard proxy) |
| `specialty-chemicals` | XLB | (sector ETF fallback — no dedicated chemical ETF without paid data) |
| `steel` | XME | SPDR S&P Metals & Mining ETF |
| `copper` | XME | SPDR S&P Metals & Mining ETF |
| `aluminum` | XME | SPDR S&P Metals & Mining ETF |

**All other industryKey values** → fall through to `SECTOR_ETF_MAP[sector]`

---

## Momentum Calculation Approach

### Recommended Metrics (display-only, display on every signal row)

| Metric | Calculation | Rationale |
|--------|-------------|-----------|
| `industry_etf` | str — resolved ETF ticker (e.g., `"XSD"`) | Tells the user which proxy was used |
| `industry_mom_20d` | `(etf.Close.iloc[-1] / etf.Close.iloc[-21] - 1) * 100` | 20-day ROC; aligns with the 5–20 day hold window |
| `industry_above_50ma` | `etf.Close.iloc[-1] > etf.Close.rolling(50).mean().iloc[-1]` | Trend direction — is the industry in a rising regime? |
| `industry_rs_spy` | `etf_mom_20d / spy_mom_20d` — ratio (>1 = outperforming) | Directional bias vs broad market |

**Why 20 days:** The swing trading hold is 5–20 days. A 20-day momentum lookback ensures the signal timescale and the holding period are on the same order of magnitude. The IBD 252-day formula is designed for 12-month positions and dampens short-term moves that are exactly what swing trading targets.

**Why ROC over RS line:** The RS line (stock/ETF price) is a cumulative ratio that requires charting to read. ROC gives a signed percentage directly comparable across industries and is trivially displayable in a table column.

**Dual lookback (optional in Phase 2):** 5-day ROC captures "hot money" momentum (recent breakout leadership). Adding both 5d and 20d in the gate_detail_json costs nothing at collection time and enables later analysis.

### Calculation Location

Extend `_sector_strength()` in `core.py` to accept an `industry_key` parameter and return additional fields. The pattern is identical to the existing sector ETF logic — `market_data` dict already holds ETF price DataFrames, so it is just a matter of adding industry ETF tickers to the `get_market_data()` fetch list.

---

## Winner vs Loser Analysis Stack

No new runtime libraries are needed. The analysis runs at report-generation time in `report.py`.

### Data Requirement

Entry-time industry momentum must be stored in the signal record at scan/backtest time. The lowest-friction storage location is `gate_detail_json` (no schema version bump). If gate_detail_json grows too large, promote `industry_etf`, `industry_mom_20d`, `industry_above_50ma` to dedicated columns in the signals table (schema version bump to v7).

### Analysis Approach

```python
# In report.py — winner/loser breakdown
winners = signals[signals['exit_reason'] == 'TARGET']
losers  = signals[signals['exit_reason'] == 'STOP']

# For each continuous metric: median comparison + percentile overlap
metrics = ['score', 'adx', 'rsi_at_entry', 'industry_mom_20d', 'atr_multiple']
for m in metrics:
    w_med = winners[m].median()
    l_med = losers[m].median()
    # Display side-by-side in report
```

For significance testing (optional, adds scipy): Mann-Whitney U test (non-parametric, appropriate for small samples with unknown distribution).

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| `info['industryKey']` → ETF proxy map | `yf.Industry(industryKey).ticker.history()` | `.ticker` returns a Yahoo Finance synthetic index symbol (`^YXXX`), not a standard ETF; price history depth is unpredictable; equal-weighted SPDR ETFs are more reliable proxies |
| 20-day ROC | IBD 252-day RS formula | 252-day window spans 12+ months; dampens the short-term moves that swing traders are entering; overkill for 5-20 day holds |
| Industry-level ETF map | GICS sector level only (11 sectors) | Explicitly rejected in PROJECT.md — "sectors are too broad to be predictive at the individual stock level"; the entire rationale for this milestone is finer granularity |
| Store in `gate_detail_json` initially | New DB columns immediately | Schema version bump adds migration risk; display-only data not warranting dedicated columns until validated as useful |
| XBI for biotechnology | IBB | XBI is equal-weighted (better for detecting broad biotech momentum vs large-cap dominance in IBB); both accessible via yfinance |
| KRE for regional banks | KBE | KRE is more granular (regional only); most SP400/500/600 banks are regional, so KRE is a better momentum proxy than the diversified KBE |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `yf.Industry().ticker` as price source | Returns Yahoo Finance synthetic index symbol, not a tradeable ETF; price history may be shallow or absent for backtesting window | Direct `yf.download(etf_ticker)` against a mapped SPDR/iShares ETF |
| IBD 252-day weighted RS formula | Designed for 12-month positions; weights 40% on the most recent 3 months which still spans ~60 trading days — too coarse for 5-20 day swings | 20-day ROC |
| 11-sector level only | PROJECT.md explicitly requires industry-group granularity; sectors mask intra-sector rotation (e.g., biotech vs healthcare providers) | Two-tier map: industry ETF primary, sector ETF fallback |
| Any paid data feed | PROJECT.md constraint: "yfinance only — no paid data feeds" | yfinance + ETF proxies |
| XNTK (SPDR NYSE Technology ETF) | Tracks NYSE Technology index, not S&P; overlap with S&P universe is partial; liquidity is lower than XSD/XSW | XSD for semiconductors, XSW for software |
| Adding industry momentum as a gate immediately | PROJECT.md out-of-scope: "display-only first; promote only after backtest evidence" — same discipline that caught the ADX and volume contraction gate removal mistakes | Display field only; gate promotion requires a separate evidence-based decision |

---

## Stack Patterns by Variant

**If industry ETF has < 50 trading days of history (new ETF or sparse data):**
- Skip `industry_above_50ma` calculation (return None)
- Still compute `industry_mom_20d` if at least 21 bars exist
- Fall back to sector ETF for the full calculation

**If `industryKey` is absent from `.info` response (rate-limited or missing data):**
- Return `None` for all industry momentum fields — same "SKIP gate" philosophy applied to earnings unknown
- Do not infer from sector alone — absence of data ≠ weak industry

**For backtesting (as_of dates in the past):**
- Industry ETF prices are sliced to the same `end=as_of_date` window as stock prices
- The ETF is already in `get_market_data()` after the initial mapping — no extra download per ticker

---

## Implementation Checklist (informing roadmap)

- [ ] Add `industry` and `industry_key` fields to `QualityInfo` dataclass
- [ ] Extend `_make_quality_info()` to extract `info.get('industry')` and `info.get('industryKey')`
- [ ] Define `INDUSTRY_ETF_MAP` dict in `core.py` alongside `SECTOR_ETF_MAP`
- [ ] Extend `get_market_data()` in `data_store.py` to include all unique industry ETF tickers
- [ ] Extend `_sector_strength()` to compute `industry_mom_20d`, `industry_above_50ma`, `industry_rs_spy`
- [ ] Add `industry_etf`, `industry_mom_20d`, `industry_above_50ma` to `gate_detail_json` (no schema bump)
- [ ] Surface fields in signal output (scan results table, web API, UI)
- [ ] Winner/loser analysis function in `report.py` using stored backtest signal metrics

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| yfinance 0.2.x | pandas 1.5+ / 2.x | `info` dict `industryKey` field available from 0.2.18+; `.Sector()` and `.Industry()` classes added in 0.2.37+ |
| yfinance 0.2.x | Python 3.9+ | No version constraint issues on Windows |
| scipy 1.11 | numpy 1.23+ | Only needed for winner/loser statistical tests; optional dependency |

---

## Sources

- `/websites/ranaroussi_github_io_yfinance` (context7, MEDIUM confidence) — `Ticker.info` field reference, `sectorKey`/`industryKey` confirmed, `yf.Sector()`/`yf.Industry()` class API
- `https://raw.githubusercontent.com/ranaroussi/yfinance/main/yfinance/const.py` (context7, MEDIUM confidence) — complete industry key taxonomy (11 sectors, ~118 industry slugs)
- Web search — SPDR S&P Select Industry ETF ticker list (LOW confidence; tickers cross-checked against known liquid ETFs)
- Web search — IBD RS methodology, 20-day lookback for swing trading (LOW confidence; practitioner sources)
- `D:/Projects/TraderAssist/scanner/core.py` — confirmed existing `SECTOR_ETF_MAP`, `_sector_strength()`, `QualityInfo`, `_make_quality_info()` structure
- `D:/Projects/TraderAssist/.planning/PROJECT.md` — constraints: yfinance-only, display-only first, industry-group granularity requirement

---
*Stack research for: TraderAssist — industry/sector momentum extension*
*Researched: 2026-06-30*
