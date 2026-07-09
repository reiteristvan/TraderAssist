# Phase 5: Sector Resolution & Data Input - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 delivers the data layer for the Weekly Seasonality Analyzer: given a `--sector` and `--universe`, resolve the universe to tickers in that sector (via a new persisted ticker→GICS-sector cache), validate each ticker has enough cached daily OHLCV history, and hand back a clean `{ticker: DataFrame}` set ready for Phase 6's statistics.

**In scope:**
- New `scanner/sector_store.py` — Parquet-cached ticker→GICS-sector lookup (yfinance `info['sector']`), mirroring `earnings_store.py`'s per-ticker cache pattern
- Sector name validation against the canonical GICS sector list, case-insensitive
- Universe file resolution (`sp400`/`sp500`/`sp600`/`all` → `universes/{name}.txt` / `universes/sp_all.txt`, via existing `load_universe_file`)
- A new `scanner/` module housing the data-loading pipeline (sector resolution + universe filtering + history validation), consumed by the root `seasonality_by_week.py` CLI
- 2-year minimum history check on top of `data_store.get_history()`'s existing 220-row floor
- Skip-and-log behavior for tickers with insufficient history or missing/corrupt cache files

**Out of scope (deferred to Phase 6+):**
- ISO-week aggregation, bootstrap statistics, significance flagging — Phase 6
- CLI table/summary output, CSV export — Phase 7
- Any change to the existing OHLCV cache (`data_store.py`) or its 220-row minimum
- Wiring into scan/backtest pipeline or schema changes — explicitly out of scope for the whole milestone

</domain>

<decisions>
## Implementation Decisions

### Sector Cache Structure
- **D-01:** One Parquet file per ticker, `data/sectors/{TICKER}.parquet` — exact structural mirror of `earnings_store.py`'s `_cache_path()` / per-ticker file pattern, not a single shared cache file. Consistent with the existing convention even though it means ~1,500 small files for `sp_all`.
- **D-02:** Valid GICS sector names for validation (SEAS-02's error-listing requirement) come from the existing `SECTOR_ETF_MAP` keys in `scanner/core.py` (11 canonical sector strings) — do not introduce a second, separately-maintained sector name list.
- **D-03:** A ticker whose sector can't be resolved (yfinance returns no `sector`, or the fetch fails) is treated like the earnings-unknown / weekly-missing-data philosophy elsewhere in the codebase: skip it silently from sector-matching (it can't match any sector filter), not an error that aborts the run.

### Module Placement
- **D-04:** The sector-resolution + universe-filtering + history-validation pipeline lives in a new `scanner/` module (not inline in the root script), matching the existing `scan.py`-is-thin / `scanner/*.py`-has-logic convention (mirrors `backtest.py`, `report.py`, `targets.py`). `seasonality_by_week.py` at repo root stays a thin CLI wrapper that calls into this module. Naming is Claude's discretion (see below) but should anticipate Phase 6 importing the same module for stats and Phase 7 for CLI output — likely one `scanner/seasonality.py` module grown across all three phases rather than a new module per phase.

### Lookback / History Validation
- **D-05:** The 2-year minimum-history rule (SEAS-04) is evaluated against a ticker's **raw cached history**, independent of `--years`: a ticker needs ≥2 years of history to be included in the analysis at all. `--years` then trims the validated history down to the requested analysis window — it does not relax or change the 2-year admission threshold.
- **D-06:** `get_history()`'s existing 220-row (~1 year) minimum is a separate, lower floor already enforced by `data_store.py`. Phase 5 adds its own explicit ≥2-year check on top of (not instead of) that floor — a ticker passing the 220-row floor can still fail the 2-year seasonality-specific check.

### Cache Population Strategy
- **D-07:** The sector cache populates **lazily, on-demand**, per ticker, the first time it's encountered during a run — mirroring `earnings_store.get_earnings_dates()`'s on-demand fetch-and-cache pattern. No separate pre-warm/build CLI subcommand for this phase. A first run against `sp500` will make up to ~500 sequential yfinance `info` calls before analysis starts; this is an accepted one-time cost, same tradeoff already made for the OHLCV cache via `scan.py refresh`.

### Claude's Discretion
- Exact name and internal structure of the new `scanner/` module (e.g. `scanner/seasonality.py` vs `scanner/seasonality_data.py`) — pick something Phase 6/7 can extend rather than re-import from a differently-named module.
- Exact function signatures for sector resolution / universe filtering / history validation.
- Whether ticker→sector fetch failures get a retry (mirroring `fetch_with_retry` in `data_store.py`) or fail fast to `None` on first error — should follow the same retry discipline as `earnings_store.py` and `data_store.py` for consistency.
- Whether "2 years" is measured in calendar days or trading days for the SEAS-04 floor.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning & Requirements
- `.planning/ROADMAP.md` §Phase 5 — Goal, success criteria (5 numbered), requirements mapping
- `.planning/REQUIREMENTS.md` §SEAS-01 through SEAS-05 — the five requirements mapped to Phase 5
- `.planning/PROJECT.md` §Current Milestone — target CLI flags (`--sector`, `--years`, `--universe`, `--output`, `--bootstrap-iters`, `--seed`) and the `scanner/sector_store.py` naming/design directive

### Codebase Extension Points (patterns to mirror)
- `scanner/earnings_store.py` — the exact Parquet per-ticker cache pattern to mirror for `scanner/sector_store.py` (`_cache_path()`, cache-hit/cache-miss branching, empty-cache-on-failure to avoid retry storms)
- `scanner/data_store.py:218` `get_history()` — reused as-is for daily OHLCV; already returns adjusted Close (`auto_adjust=True` at `data_store.py:119`) and enforces a 220-row floor (`_MIN_ROWS`, `data_store.py:25`)
- `scanner/data_store.py:51` `fetch_with_retry()` — retry pattern to reuse for any new yfinance call in `sector_store.py`
- `scanner/core.py:51` `SECTOR_ETF_MAP` — canonical 11-entry GICS sector name list; source of truth for SEAS-02's "list of valid sector names" error message
- `scanner/universe.py:112` `load_universe_file()` — reused as-is to resolve `--universe` to a ticker list from `universes/{sp400,sp500,sp600}.txt` or `universes/sp_all.txt`
- `.planning/milestones/v1.0-phases/01-industry-classification-etf-data-layer/01-CONTEXT.md` — prior phase that added a similar yfinance-info-derived field (`industry_key`) to the pipeline; useful precedent for how per-ticker classification data was threaded through without schema changes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `earnings_store.py`'s full file (`get_earnings_dates`, `_cache_path`, `_CACHE_DIR = Path("data/earnings")`) — direct structural template for `sector_store.py` with `_CACHE_DIR = Path("data/sectors")`
- `SECTOR_ETF_MAP` (`scanner/core.py:51`) — reuse directly as the valid-sector-names source; do not duplicate the list
- `load_universe_file()` (`scanner/universe.py:112`) — already normalizes tickers (uppercase, strips reserved names) and skips comment lines; no changes needed
- `get_history()` (`scanner/data_store.py:218`) — already handles cache-miss fetch, reserved-name filtering, and returns `None` on failure/insufficient rows; Phase 5 layers a 2-year check on top of its return value

### Established Patterns
- Parquet cache files always live under `data/{purpose}/` (`data/ohlcv/`, `data/earnings/`, and now `data/sectors/`) — one directory per cache type, `Path.mkdir(parents=True, exist_ok=True)` on first write
- "SKIP, don't fail" philosophy for missing/ambiguous data (weekly-missing-data gate, earnings-unknown gate) — Phase 5's missing-sector and missing-history handling should follow the same discipline: log and skip, never abort the whole run for one bad ticker
- `scan.py` is a thin CLI dispatcher; all real logic lives in `scanner/*.py` modules — `seasonality_by_week.py` should follow the same shape

### Integration Points
- `seasonality_by_week.py` (new, repo root) calls into the new `scanner/` seasonality module, which calls `sector_store.py` + `universe.py` + `data_store.get_history()`
- No changes required to `data_store.py`, `store_db.py`, or any DB schema — this phase is purely additive, file-cache-based, and fully outside the `scan.py`/web pipeline

</code_context>

<specifics>
## Specific Ideas

No specific UI/output requirements at this phase — those are Phase 7. The main "I want it like X" signal from this discussion is explicit: mirror `earnings_store.py`'s structure and philosophy as closely as possible rather than inventing a new caching approach, and keep `seasonality_by_week.py` itself thin per the existing `scan.py` convention.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 5-Sector Resolution & Data Input*
*Context gathered: 2026-07-09*
