# Codebase Concerns

**Analysis Date:** 2026-07-02

---

## Tech Debt

**`yfinance` import rule violated in `core.py`:**
- Issue: CLAUDE.md states "No `yf.` imports outside `data_store.py` / `earnings_store.py`" but `scanner/core.py` imports yfinance at module level (line 15) and calls `yf.Ticker(ticker).info` and `yf.Ticker(ticker).calendar` directly inside `_make_quality_info()` and `_days_to_earnings()`.
- Files: `scanner/core.py` lines 15, 484, 517
- Impact: The convention exists to make the yfinance dependency swappable by changing one module. With live calls in `core.py`, that swap becomes a two-module change. Also breaks the stated testability boundary.
- Fix approach: Move `_make_quality_info()` and `_days_to_earnings()` (or the raw yfinance calls inside them) into `data_store.py`. Re-export from `core.py` if needed for import compatibility.

**`industry_etf` and `industry_rs_spy` computed but not persisted:**
- Issue: `_industry_strength()` in `scanner/core.py` returns a 4-key dict including `industry_etf` (which ETF proxy was selected) and `industry_rs_spy` (industry momentum relative to SPY). Both are assigned to in-memory row dicts but no matching columns exist in the `signals` table. `insert_signal` never writes them.
- Files: `scanner/core.py` lines 289–311, 713–714; `scanner/store_db.py` lines 214–227
- Impact: The ETF proxy actually used is invisible post-scan. If industry momentum data is later investigated, there is no way to know which ETF produced the stored `industry_momentum` value. `industry_rs_spy` is lost entirely.
- Fix approach: Add `industry_etf TEXT` and `industry_rs_spy REAL` columns in a schema v10 migration. Include them in `insert_signal` and the corresponding `ON CONFLICT DO UPDATE` in `store_db.py`.

**API migration layer is stale (schema v6 only):**
- Issue: `web/api/db/index.js` `_applyMigrations()` function only knows about the migration to schema v6 (adds `notes` column). Python `store_db.py` is at schema v9 (adds 4 industry columns). If the write DB connection is created before Python has run `migrate()`, the API's migration leaves the DB at v6.
- Files: `web/api/db/index.js` lines 69–75; `scanner/store_db.py` line 15
- Impact: Ordering assumption is safe in practice (Python always runs first), but the API's migration guard is a maintenance trap — it will silently diverge further with each new Python migration.
- Fix approach: Either remove the `_applyMigrations` call from the API entirely (rely on Python exclusively), or keep the API migration in sync with Python's `_SCHEMA_VERSION` constant.

**Relative path coupling requires CWD = project root:**
- Issue: `scanner/data_store.py` uses `Path("data/ohlcv")`, `scanner/earnings_store.py` uses `Path("data/earnings")`, and `scanner/store_db.py` uses `Path("data/scanner.db")` — all relative to the process working directory.
- Files: `scanner/data_store.py` line 24; `scanner/earnings_store.py` line 19; `scanner/store_db.py` line 14
- Impact: Running any scanner module from a different CWD (e.g., from inside `scanner/`) will silently create a second `data/` directory at that location rather than raising an error. Has caused confusion during backtest runs in subdirectories.
- Fix approach: Anchor paths to `Path(__file__).parent.parent / "data"` in each module. Alternatively, pass the root path via an env var and validate it at startup.

**Global `warnings.filterwarnings` suppression:**
- Issue: `scanner/core.py` (lines 17–18) and `scanner/backtest.py` (lines 70–71) suppress all `FutureWarning` and `UserWarning` at process level using `warnings.filterwarnings("ignore", ...)`.
- Files: `scanner/core.py` lines 17–18; `scanner/backtest.py` lines 70–71
- Impact: Suppresses genuine deprecation warnings from pandas and yfinance that signal upcoming breaking changes. When a new library version introduces a silent behavior change previously warned about, there is no notification.
- Fix approach: Scope the suppression to only the specific yfinance call sites using `with warnings.catch_warnings():` context managers, or filter only on specific message patterns.

---

## Known Bugs

**`make_contexts` live-mode `as_of_date` can differ per ticker:**
- Symptoms: When `as_of=None` (live scan), each ticker's `as_of_date` is derived from `df.index[-1].date()`. Tickers whose Parquet cache is a few days stale get a different `as_of_date` than freshly-refreshed tickers. Market data is fetched once with `end=None` (entire history), so the market context is consistent, but per-ticker `days_to_earnings` is computed against divergent dates.
- Files: `scanner/core.py` lines 580–591
- Trigger: Any ticker whose cache is not current to the same date as the majority of the universe — common after weekend or holiday gaps.
- Workaround: Run `python scan.py refresh` before `scan.py scan` to normalise all caches to the same trailing date.

---

## Security Considerations

**CORS origin hardcoded to `http://localhost:4200`:**
- Risk: If the API is exposed beyond localhost (e.g., local network access), no auth protects it.
- Files: `web/api/app.js` line 18
- Current mitigation: API is intended for localhost only; no credentials or sensitive financial data visible to third parties beyond signal history.
- Recommendations: Acceptable for a personal local tool. Document that the API must not be exposed on a network interface.

**No rate limiting or request validation on API:**
- Risk: The Express API has no rate limiting, no request-size limit beyond Express defaults, and no auth. Any process on the local machine can read or write signals/jobs.
- Files: `web/api/app.js`, `web/api/routes/jobs.js`
- Current mitigation: Localhost-only CORS and OS-level access controls.
- Recommendations: Add `express-rate-limit` if the tool is ever exposed beyond the developer machine.

---

## Performance Bottlenecks

**`_make_quality_info()` is called serially with a sleep per ticker:**
- Problem: Each ticker in `make_contexts()` triggers one `yf.Ticker(ticker).info` call with a `quality_pause=0.15s` sleep between calls plus up to 3 retry attempts at 1s/2s/4s each on failure. A 500-ticker scan takes at minimum ~75 seconds just in quality fetch pauses, plus network latency.
- Files: `scanner/core.py` lines 473–511, 566–593
- Cause: yfinance rate-limiting requires throttling; no result caching across calls.
- Improvement path: Cache `QualityInfo` results keyed by ticker to a short-lived in-process dict (TTL ~1 day) so repeat scans within the same session skip re-fetching. Alternatively, batch quality data into a separate Parquet cache similar to OHLCV.

**`get_market_data()` loads all 30 ETFs for every ticker in single-ticker diagnostic mode:**
- Problem: `make_context()` (single-ticker path, used for verbose diagnose) calls `get_market_data(end=as_of_date)` which reads up to 30 Parquet files regardless of how many are actually needed by the strategy.
- Files: `scanner/data_store.py` lines 290–297; `scanner/core.py` lines 547–551
- Cause: Batch path (`make_contexts`) loads market data once — efficient. Single-ticker path duplicates the full load.
- Improvement path: Lazy-load individual ETF frames inside `_industry_strength()` and `_sector_strength()` when only a single ticker is being evaluated.

---

## Fragile Areas

**`_days_to_earnings()` in live mode — yfinance `calendar` API shape is unstable:**
- Files: `scanner/core.py` lines 514–536
- Why fragile: The function handles three different return types for `yf.Ticker().calendar` (dict, DataFrame, None) because yfinance changed the return format across versions. The handling has multiple isinstance checks and falls through to `return None` on any exception. A new yfinance version could change the format again and silently cause all earnings gates to SKIP.
- Safe modification: Any change to earnings gate logic must include a test that asserts the `days_to_earnings` value is non-None for a known ticker before and after the change.
- Test coverage: `tests/test_earnings_store.py` covers the historical path; live `_days_to_earnings()` has no dedicated test — it is only indirectly tested via `tests/test_core.py` with monkeypatched `calendar`.

**`_attach_industry_rank_pct()` mutates shared row dicts in-place:**
- Files: `scanner/core.py` lines 315–339
- Why fragile: The function mutates list-of-dict rows in-place after the main loop. Any code path that calls `run_scan()` and then inspects `industry_rank_pct` before `_attach_industry_rank_pct` has been called will see `None`. The comment "Must be called POST-LOOP" exists but is not enforced structurally.
- Safe modification: Do not add early-return paths from `run_scan()` that bypass line 727.

**`VOL_CONTRACTION_MAX` only applied in pullback, not breakout:**
- Files: `scanner/strategies/pullback.py` line 200; `scanner/strategies/breakout.py` (not present)
- Why fragile: The constant is defined in `scanner/core.py` but only imported by `pullback.py`. This is likely intentional (breakout is about expansion, not contraction) but is not documented near the constant. A future developer adding volume logic to breakout may inadvertently apply the wrong threshold.
- Safe modification: Add a comment to `VOL_CONTRACTION_MAX` in `core.py` noting it is pullback-only by design.

---

## Scaling Limits

**SQLite write concurrency — single writer:**
- Current capacity: SQLite WAL mode is not explicitly enabled. With the default journal mode, concurrent writes from `scan.py` and the API's job enqueue path (`getWriteDb()`) can produce `SQLITE_BUSY` errors.
- Limit: Any overlapping write from two processes.
- Scaling path: Enable WAL mode (`PRAGMA journal_mode=WAL`) in `store_db.get_connection()`. The CLAUDE.md notes SQLite is swappable to Postgres; that would resolve concurrent write limits entirely.

**yfinance rate limiting scales poorly beyond ~500 tickers:**
- Current capacity: SP400 + SP500 + SP600 = ~1400 tickers. At 0.15s pause per ticker plus network time, a full-universe quality fetch takes 3–5 minutes. yfinance rate limits become more aggressive at this scale.
- Limit: Quality fetch failures increase beyond ~500 tickers in a single session.
- Scaling path: Add a persistent quality cache (Parquet keyed by ticker, TTL 24h) to skip re-fetching tickers whose fundamentals were recently loaded.

---

## Dependencies at Risk

**`yfinance` — undocumented internal API surface:**
- Risk: `yf.Ticker().info`, `yf.Ticker().calendar`, and `yf.Ticker().history()` are the only data sources. yfinance reverse-engineers Yahoo Finance's private API; Yahoo has changed response formats multiple times without notice.
- Impact: A yfinance version bump can break `_make_quality_info()`, `_days_to_earnings()`, or OHLCV fetches simultaneously. There is no fallback data source.
- Migration plan: Pin `yfinance` to the tested version in `requirements.txt` (not currently pinned with an exact version), and validate each yfinance upgrade with `pytest -q` plus a live smoke test on a sample ticker before upgrading.

---

## Open Items / Deferred Decisions

**E3.4 — Breakout strategy gate analysis (deferred):**
- Problem: The RS vs SPY, sector strength, and weekly trend gates on the breakout strategy have not been validated against backtest data. Their contribution to signal quality (positive or negative) is unknown.
- Blocks: A data-backed decision on whether to retain, remove, or weight these gates.
- Files: `scanner/strategies/breakout.py`; noted in `CLAUDE.md` lines 101–106
- Priority: High — these gates affect every breakout signal. Without attribution data, the gate set may be excluding good setups or including bad ones.

---

## Test Coverage Gaps

**Live `_days_to_earnings()` not directly tested:**
- What's not tested: The live-mode code path in `scanner/core.py:514–536` that calls `yf.Ticker().calendar`. Only the historical path (via `earnings_store`) is covered by `tests/test_earnings_store.py`.
- Files: `scanner/core.py` lines 514–536
- Risk: yfinance `calendar` format changes break earnings gate silently (returns `None` = SKIP for all tickers).
- Priority: Medium.

**`web/api/db/index.js` `_applyMigrations()` not tested:**
- What's not tested: The migration guard in the API's write DB path.
- Files: `web/api/db/index.js` lines 69–75
- Risk: If the guard falls out of sync with Python migrations (already the case at v9 vs v6), the API could corrupt schema_version silently.
- Priority: Low (personal tool; Python always migrates first in practice).

**Industry momentum fields under scanner.db schema v9 not back-filled:**
- What's not tested: Signals stored before schema v9 have NULL for all `industry_*` columns. No migration or back-fill step exists.
- Files: `scanner/store_db.py` lines 159–165
- Risk: Backtest reports that compare old vs new signals will treat NULL industry fields as missing data rather than "computed but not stored," which could skew winner/loser analysis.
- Priority: Low for new projects; Medium if historical backtests are being compared against post-v9 runs.

---

*Concerns audit: 2026-07-02*
