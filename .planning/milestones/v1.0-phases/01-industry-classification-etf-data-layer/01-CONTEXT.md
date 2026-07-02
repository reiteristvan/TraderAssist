# Phase 1: Industry Classification + ETF Data Layer - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers the data layer foundation only: the pipeline gains the ability to read each ticker's industry group from yfinance (`info['industry']` and `info['industryKey']`) and store it in `QualityInfo`, and Parquet-cached ETF price series for all covered industry groups are available via `get_market_data()` for Phase 2's momentum computation.

**In scope:**
- Add `industry` and `industry_key` fields to `QualityInfo` dataclass
- Extend `_make_quality_info()` to fetch both fields from yfinance `info` dict
- Define `INDUSTRY_ETF_MAP` in `core.py` (full research map)
- Extend `_MARKET_SYMBOLS` in `data_store.py` with deduplicated industry ETF tickers
- Define the ETF resolution lookup chain with tests

**Out of scope (deferred to Phase 2+):**
- DB schema changes — schema v7 ships in Phase 2
- Momentum score computation (20-day ROC, above/below 50 MA, rank percentile)
- Look-ahead bias prevention — Phase 2 concern
- CLI display or web UI changes — Phase 3
- Industry ETF usage in `_sector_strength()` or any new strength function

</domain>

<decisions>
## Implementation Decisions

### ETF Map Scope
- **D-01:** Ship the **full INDUSTRY_ETF_MAP** from the CLAUDE.md research — all ~25+ `industryKey` → ETF entries covering every sector represented in the research doc (~17 unique ETF tickers: XSD, XSW, XBI, XPH, XHE, XHS, KRE, KBE, KIE, KCE, XHB, XRT, XAR, XOP, XES, XLE, GDX, XME plus any others in the research). Do not implement a starter set.
- **D-02:** **Deduplicate `_MARKET_SYMBOLS`** — build the union of the current sector ETF list and all new industry ETF tickers. No ticker should appear more than once in `_MARKET_SYMBOLS`. Sector ETFs already in the list (XLK, XLF, XLE, etc.) are not duplicated even if they appear as fallback entries in INDUSTRY_ETF_MAP.
- **D-03:** **Sector-level fallback entries live in the map itself** — industries that have no dedicated ETF (e.g., `"oil-gas-integrated": "XLE"`, `"specialty-chemicals": "XLB"`) are encoded as explicit entries in `INDUSTRY_ETF_MAP`. The map is the single source of truth; no separate fallback table.

### QualityInfo Fields
- **D-04:** Add **two new `Optional[str]` fields** to `QualityInfo`, both defaulting to `None`:
  - `industry: Optional[str]` — human-readable name from `info['industry']` (e.g. `"Semiconductors"`)
  - `industry_key: Optional[str]` — slug from `info['industryKey']` (e.g. `"semiconductors"`)
- **D-05:** Field naming follows the existing bare convention (matches `sector`, not `sector_name`). `industry` for display, `industry_key` for ETF map lookup.

### ETF Fallback Resolution
- **D-06:** When `industry_key is None` (yfinance returned no industry classification) → **return `None` immediately**. No fallback to sector ETF. Sector-level ETF coverage is `_sector_strength()`'s job; the industry ETF resolution function is a separate, narrower concern.
- **D-07:** When `industry_key` is a known string, apply the **two-step lookup chain**:
  1. `INDUSTRY_ETF_MAP.get(industry_key)` — explicit entry (may resolve to a sector ETF for industries without dedicated ETFs)
  2. If that returns `None` (key not in map at all): `SECTOR_ETF_MAP.get(sector)`
  3. If still `None`: return `None` — no ETF available for computation

  This chain must be unit-tested per success criterion 4 (key in map → resolved; key not in map → sector fallback; neither → None).

### Claude's Discretion
- Where exactly to place the ETF resolution helper function (`core.py` alongside `SECTOR_ETF_MAP` is implied by the research but exact function name/signature is up to the planner)
- Whether `industry` and `industry_key` use `field(default=None)` or `= None` syntax in the frozen dataclass

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning & Requirements
- `.planning/ROADMAP.md` §Phase 1 — Goal, success criteria (4 numbered), and mode for this phase
- `.planning/REQUIREMENTS.md` §IND-01 — The single requirement mapped to Phase 1

### Research & Architecture
- `.claude/CLAUDE.md` — Full `INDUSTRY_ETF_MAP` entries (all sector subsections), `INDUSTRY_ETF_MAP` strategy rationale, `Momentum Calculation Approach` table, `Implementation Checklist`, `What NOT to Use` table, `Version Compatibility` table

### Codebase Extension Points
- `scanner/core.py` — `SECTOR_ETF_MAP` (dict pattern to mirror), `QualityInfo` dataclass (where fields are added), `_make_quality_info()` (where yfinance fetches happen), `_sector_strength()` (pattern for ETF-based computation)
- `scanner/data_store.py` — `_MARKET_SYMBOLS` list (extend with deduplicated industry ETFs), `get_market_data()` (automatically includes new symbols after list extension), `_MARKET_SYMBOLS` (lines 26–29)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SECTOR_ETF_MAP` (`scanner/core.py:51`) — exact pattern to mirror for `INDUSTRY_ETF_MAP`; place adjacent
- `_sector_strength()` (`scanner/core.py:215`) — ETF lookup + `market_data.get(etf)` pattern; Phase 2 industry computation will mirror this
- `_make_quality_info()` (`scanner/core.py:346`) — already fetches `info.get("sector")`; add `info.get('industry')` and `info.get('industryKey')` in the same block

### Established Patterns
- `QualityInfo` is `@dataclass(frozen=True)` — all existing tests that construct it will need the two new fields (with `None` defaults) or will break; planner must audit test callsites in `tests/`
- `_MARKET_SYMBOLS` is a plain list; `get_market_data()` iterates it — simply extending the list is sufficient; no other changes needed in `data_store.py`
- `_make_quality_info()` has a 3-retry loop with rate-limit detection (`operatingIncome`, `forwardEps`, `marketCap` all None = empty dict); the `industry` / `industry_key` fields are fetched from the same `info` dict without extra network calls
- `fetch_with_retry` in `data_store.py` (line 34) — use for any new yfinance download in the Parquet cache layer

### Integration Points
- `get_market_data(end=as_of_date)` is called in `make_contexts()` and the backtest loop (`scanner/core.py:415, 445`) — the additional ETF frames will be present automatically after `_MARKET_SYMBOLS` extension; Phase 2 reads them by key
- `QualityInfo` is constructed only in `_make_quality_info()` and test fixtures in `tests/` — those are the only callsites to update

</code_context>

<specifics>
## Specific Ideas

- The `.claude/CLAUDE.md` research doc contains a complete proposed `INDUSTRY_ETF_MAP` broken into sector subsections (Technology, Healthcare, Financial Services, Consumer Cyclical, Industrials, Energy, Basic Materials, Real Estate). Agents should copy this map verbatim rather than re-deriving it.
- The two-step resolution chain (D-07) should be a named helper function (e.g., `resolve_industry_etf(industry_key, sector)`) rather than inline logic, because the unit test for success criterion 4 needs a callable to test directly.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Industry Classification + ETF Data Layer*
*Context gathered: 2026-06-30*
