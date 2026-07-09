# Phase 5: Sector Resolution & Data Input - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 5-Sector Resolution & Data Input
**Areas discussed:** Sector cache layout, Module placement, Lookback rule interaction, Sector cache warm-up strategy

---

## Sector cache file layout

| Option | Description | Selected |
|--------|-------------|----------|
| One file per ticker | Exact mirror of earnings_store.py: data/sectors/{TICKER}.parquet, one row. Simple, consistent with existing convention, but ~1,500 tiny files for sp_all. | ✓ |
| One shared Parquet file | data/sectors/sector_cache.parquet with all ticker→sector rows. Fewer files, easy to inspect/grep, single read on startup — but diverges from the earnings_store.py per-ticker pattern PROJECT.md names as the model. | |

**User's choice:** One file per ticker.
**Notes:** Chosen to keep exact structural consistency with `earnings_store.py`, which PROJECT.md explicitly names as the model.

---

## Module placement for data-loading logic

| Option | Description | Selected |
|--------|-------------|----------|
| New scanner/ module | e.g. scanner/seasonality.py holds the data-loading logic; seasonality_by_week.py at repo root is a thin CLI wrapper. Matches the existing scan.py-is-thin, scanner/*.py-has-logic convention, and makes Phase 6/7 stats testable against it directly. | ✓ |
| Inline in the root script | All logic lives directly in seasonality_by_week.py since PROJECT.md describes it as a standalone script. Simpler for a single-purpose diagnostic tool, but breaks from the scan.py convention and means Phase 6 tests would need to import from a root-level script. | |

**User's choice:** New scanner/ module (recommended option).
**Notes:** Keeps Phase 6/7 able to import and test the same module rather than reaching into a root-level script.

---

## Lookback rule interaction (SEAS-04 vs --years)

| Option | Description | Selected |
|--------|-------------|----------|
| Always require ≥2yr of raw history | Regardless of --years, a ticker needs at least 2 years of cached history to be included at all. --years then trims the analysis window from that validated set. | ✓ |
| Require ≥2yr within the requested window | If a user passes --years 3, a ticker must have ≥2 of those 3 years populated. A ticker with 5 years of history but only 1 year inside a --years 1 request would be skipped. | |

**User's choice:** Always require ≥2yr of raw history, independent of --years.
**Notes:** --years trims the validated window after admission; it does not relax the 2-year admission threshold.

---

## Sector cache warm-up strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy, on-demand per ticker | Mirrors earnings_store.get_earnings_dates: fetch-and-cache the first time a ticker is seen, during the run itself. Simple, no new CLI surface, but a fresh sp500 run makes ~500 sequential yfinance info calls before analysis starts. | ✓ |
| Same lazy approach, just confirm it's fine | Confirming the on-demand approach is acceptable for now (no separate pre-warm subcommand needed) — first run will be slow but only once, same tradeoff as the existing OHLCV cache. | ✓ |

**User's choice:** Lazy, on-demand population. No pre-warm CLI subcommand for this phase.
**Notes:** Accepted as the same one-time-cost tradeoff already made for the OHLCV cache via `scan.py refresh`.

---

## Claude's Discretion

- Exact name of the new `scanner/` module (leaning `scanner/seasonality.py`, to be grown across Phases 5–7 rather than renamed per phase).
- Exact function signatures for sector resolution / universe filtering / history validation.
- Retry discipline for sector fetch failures (should mirror `fetch_with_retry` used elsewhere).
- Whether "2 years" is measured in calendar days or trading days.

## Deferred Ideas

None — discussion stayed within phase scope.
