<!-- GSD:project-start source:PROJECT.md -->

## Project

**TraderAssist — Signal Quality Milestone**

TraderAssist is a personal swing trading scanner that identifies pullback and breakout setups across S&P 400/500/600 universes. It runs nightly scans, generates signals with gate-based filtering, backtests strategies over historical data, and displays results through a web UI. The owner uses it to surface actionable trade candidates with defined risk parameters.

**Core Value:** Surface high-quality swing trade setups where the signal has a genuine edge — not just gate compliance.

### Constraints

- **Data source**: yfinance only — no paid data feeds; industry group data must be derivable from yfinance or the tickers themselves
- **Gate stability**: Do not change existing gate thresholds or score formulas without an explicit task backed by data
- **Test suite**: `pytest -q` must stay green after every Python change; `npm test` and `ng test` must stay green after web changes
- **Architecture**: New display fields flow through the same signal pipeline (scanner → DB → API → UI); no new tables without schema version bump

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

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

## Data Classification: How to Get `industryKey`

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

## Industry ETF Proxy Map

### Strategy

### Recommended `INDUSTRY_ETF_MAP` (industryKey → ETF ticker)

| industryKey | ETF | Name |
|------------|-----|------|
| `semiconductors` | XSD | SPDR S&P Semiconductor ETF |
| `semiconductor-equipment-materials` | XSD | SPDR S&P Semiconductor ETF |
| `software-infrastructure` | XSW | SPDR S&P Software & Services ETF |
| `software-application` | XSW | SPDR S&P Software & Services ETF |
| `information-technology-services` | XSW | SPDR S&P Software & Services ETF |
| industryKey | ETF | Name |
|------------|-----|------|
| `biotechnology` | XBI | SPDR S&P Biotech ETF (equal-weight; more volatile than IBB but broader) |
| `drug-manufacturers-general` | XPH | SPDR S&P Pharmaceuticals ETF |
| `drug-manufacturers-specialty-generic` | XPH | SPDR S&P Pharmaceuticals ETF |
| `medical-devices` | XHE | SPDR S&P Health Care Equipment ETF |
| `medical-instruments-supplies` | XHE | SPDR S&P Health Care Equipment ETF |
| `healthcare-plans` | XHS | SPDR S&P Health Care Services ETF |
| `medical-care-facilities` | XHS | SPDR S&P Health Care Services ETF |
| industryKey | ETF | Name |
|------------|-----|------|
| `banks-regional` | KRE | SPDR S&P Regional Banking ETF |
| `banks-diversified` | KBE | SPDR S&P Bank ETF |
| `insurance-property-casualty` | KIE | SPDR S&P Insurance ETF |
| `insurance-life` | KIE | SPDR S&P Insurance ETF |
| `insurance-diversified` | KIE | SPDR S&P Insurance ETF |
| `capital-markets` | KCE | SPDR S&P Capital Markets ETF |
| `financial-data-stock-exchanges` | KCE | SPDR S&P Capital Markets ETF |
| industryKey | ETF | Name |
|------------|-----|------|
| `residential-construction` | XHB | SPDR S&P Homebuilders ETF |
| `specialty-retail` | XRT | SPDR S&P Retail ETF |
| `department-stores` | XRT | SPDR S&P Retail ETF |
| `internet-retail` | XRT | SPDR S&P Retail ETF |
| industryKey | ETF | Name |
|------------|-----|------|
| `aerospace-defense` | XAR | SPDR S&P Aerospace & Defense ETF |
| industryKey | ETF | Name |
|------------|-----|------|
| `oil-gas-e-p` | XOP | SPDR S&P Oil & Gas E&P ETF |
| `oil-gas-integrated` | XLE | (sector ETF fallback — no dedicated sub-sector ETF) |
| `oil-gas-equipment-services` | XES | SPDR S&P Oil & Gas Equipment & Services ETF |
| `oil-gas-midstream` | XLE | (sector ETF fallback) |
| industryKey | ETF | Name |
|------------|-----|------|
| `gold` | GDX | VanEck Gold Miners ETF (not SPDR but de-facto standard proxy) |
| `specialty-chemicals` | XLB | (sector ETF fallback — no dedicated chemical ETF without paid data) |
| `steel` | XME | SPDR S&P Metals & Mining ETF |
| `copper` | XME | SPDR S&P Metals & Mining ETF |
| `aluminum` | XME | SPDR S&P Metals & Mining ETF |

## Momentum Calculation Approach

### Recommended Metrics (display-only, display on every signal row)

| Metric | Calculation | Rationale |
|--------|-------------|-----------|
| `industry_etf` | str — resolved ETF ticker (e.g., `"XSD"`) | Tells the user which proxy was used |
| `industry_mom_20d` | `(etf.Close.iloc[-1] / etf.Close.iloc[-21] - 1) * 100` | 20-day ROC; aligns with the 5–20 day hold window |
| `industry_above_50ma` | `etf.Close.iloc[-1] > etf.Close.rolling(50).mean().iloc[-1]` | Trend direction — is the industry in a rising regime? |
| `industry_rs_spy` | `etf_mom_20d / spy_mom_20d` — ratio (>1 = outperforming) | Directional bias vs broad market |

### Calculation Location

## Winner vs Loser Analysis Stack

### Data Requirement

### Analysis Approach

# In report.py — winner/loser breakdown

# For each continuous metric: median comparison + percentile overlap

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| `info['industryKey']` → ETF proxy map | `yf.Industry(industryKey).ticker.history()` | `.ticker` returns a Yahoo Finance synthetic index symbol (`^YXXX`), not a standard ETF; price history depth is unpredictable; equal-weighted SPDR ETFs are more reliable proxies |
| 20-day ROC | IBD 252-day RS formula | 252-day window spans 12+ months; dampens the short-term moves that swing traders are entering; overkill for 5-20 day holds |
| Industry-level ETF map | GICS sector level only (11 sectors) | Explicitly rejected in PROJECT.md — "sectors are too broad to be predictive at the individual stock level"; the entire rationale for this milestone is finer granularity |
| Store in `gate_detail_json` initially | New DB columns immediately | Schema version bump adds migration risk; display-only data not warranting dedicated columns until validated as useful |
| XBI for biotechnology | IBB | XBI is equal-weighted (better for detecting broad biotech momentum vs large-cap dominance in IBB); both accessible via yfinance |
| KRE for regional banks | KBE | KRE is more granular (regional only); most SP400/500/600 banks are regional, so KRE is a better momentum proxy than the diversified KBE |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `yf.Industry().ticker` as price source | Returns Yahoo Finance synthetic index symbol, not a tradeable ETF; price history may be shallow or absent for backtesting window | Direct `yf.download(etf_ticker)` against a mapped SPDR/iShares ETF |
| IBD 252-day weighted RS formula | Designed for 12-month positions; weights 40% on the most recent 3 months which still spans ~60 trading days — too coarse for 5-20 day swings | 20-day ROC |
| 11-sector level only | PROJECT.md explicitly requires industry-group granularity; sectors mask intra-sector rotation (e.g., biotech vs healthcare providers) | Two-tier map: industry ETF primary, sector ETF fallback |
| Any paid data feed | PROJECT.md constraint: "yfinance only — no paid data feeds" | yfinance + ETF proxies |
| XNTK (SPDR NYSE Technology ETF) | Tracks NYSE Technology index, not S&P; overlap with S&P universe is partial; liquidity is lower than XSD/XSW | XSD for semiconductors, XSW for software |
| Adding industry momentum as a gate immediately | PROJECT.md out-of-scope: "display-only first; promote only after backtest evidence" — same discipline that caught the ADX and volume contraction gate removal mistakes | Display field only; gate promotion requires a separate evidence-based decision |

## Stack Patterns by Variant

- Skip `industry_above_50ma` calculation (return None)
- Still compute `industry_mom_20d` if at least 21 bars exist
- Fall back to sector ETF for the full calculation
- Return `None` for all industry momentum fields — same "SKIP gate" philosophy applied to earnings unknown
- Do not infer from sector alone — absence of data ≠ weak industry
- Industry ETF prices are sliced to the same `end=as_of_date` window as stock prices
- The ETF is already in `get_market_data()` after the initial mapping — no extra download per ticker

## Implementation Checklist (informing roadmap)

- [ ] Add `industry` and `industry_key` fields to `QualityInfo` dataclass
- [ ] Extend `_make_quality_info()` to extract `info.get('industry')` and `info.get('industryKey')`
- [ ] Define `INDUSTRY_ETF_MAP` dict in `core.py` alongside `SECTOR_ETF_MAP`
- [ ] Extend `get_market_data()` in `data_store.py` to include all unique industry ETF tickers
- [ ] Extend `_sector_strength()` to compute `industry_mom_20d`, `industry_above_50ma`, `industry_rs_spy`
- [ ] Add `industry_etf`, `industry_mom_20d`, `industry_above_50ma` to `gate_detail_json` (no schema bump)
- [ ] Surface fields in signal output (scan results table, web API, UI)
- [ ] Winner/loser analysis function in `report.py` using stored backtest signal metrics

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| yfinance 0.2.x | pandas 1.5+ / 2.x | `info` dict `industryKey` field available from 0.2.18+; `.Sector()` and `.Industry()` classes added in 0.2.37+ |
| yfinance 0.2.x | Python 3.9+ | No version constraint issues on Windows |
| scipy 1.11 | numpy 1.23+ | Only needed for winner/loser statistical tests; optional dependency |

## Sources

- `/websites/ranaroussi_github_io_yfinance` (context7, MEDIUM confidence) — `Ticker.info` field reference, `sectorKey`/`industryKey` confirmed, `yf.Sector()`/`yf.Industry()` class API
- `https://raw.githubusercontent.com/ranaroussi/yfinance/main/yfinance/const.py` (context7, MEDIUM confidence) — complete industry key taxonomy (11 sectors, ~118 industry slugs)
- Web search — SPDR S&P Select Industry ETF ticker list (LOW confidence; tickers cross-checked against known liquid ETFs)
- Web search — IBD RS methodology, 20-day lookback for swing trading (LOW confidence; practitioner sources)
- `D:/Projects/TraderAssist/scanner/core.py` — confirmed existing `SECTOR_ETF_MAP`, `_sector_strength()`, `QualityInfo`, `_make_quality_info()` structure
- `D:/Projects/TraderAssist/.planning/PROJECT.md` — constraints: yfinance-only, display-only first, industry-group granularity requirement

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
