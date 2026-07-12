# Phase 5: Sector Resolution & Data Input - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 3 (new)
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `scanner/sector_store.py` | service (cache/model) | file-I/O (Parquet per-ticker cache) | `scanner/earnings_store.py` | exact |
| `scanner/seasonality.py` (new, name is Claude's discretion — anticipate Phase 6/7 growth) | service (pipeline/orchestration) | transform / batch | `scanner/backtest.py` (module shape: thin scan.py → logic in scanner/*.py) + `scanner/universe.py` (audit-style skip/log loop) | role-match |
| `seasonality_by_week.py` (new, repo root) | CLI / route (thin dispatcher) | request-response (CLI args → stdout) | `scan.py` (`cmd_*` + `build_parser` + `main`) | exact (structural convention only — this phase needs just one subcommand-less thin wrapper, not the full multi-command dispatcher) |

## Pattern Assignments

### `scanner/sector_store.py` (service, file-I/O)

**Analog:** `scanner/earnings_store.py` (full file, 101 lines — read in full, this is the direct structural template per D-01/D-07)

**Imports pattern** (`earnings_store.py:1-16`):
```python
"""E5.3 — Cached earnings dates.

Parquet-cached historical earnings dates, used to compute days_to_earnings
for historical EvalContexts. See CLAUDE.md EPIC E5.3.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from scanner.data_store import fetch_with_retry

_log = logging.getLogger("scanner.data")
_CACHE_DIR = Path("data/earnings")
_SPARSE_DAYS = 90  # if latest known date is >90 days before as_of, return None
```
For `sector_store.py`: mirror exactly, swap `_CACHE_DIR = Path("data/sectors")`, drop `_SPARSE_DAYS` (no analog concept for sector), logger name can stay `scanner.data` for consistency with both `data_store.py` and `earnings_store.py`.

**Cache path pattern** (`earnings_store.py:23-24`):
```python
def _cache_path(ticker: str) -> Path:
    return _CACHE_DIR / f"{ticker.upper()}_earnings.parquet"
```
Mirror as `f"{ticker.upper()}.parquet"` or `f"{ticker.upper()}_sector.parquet"` under `data/sectors/` (D-01 says `data/sectors/{TICKER}.parquet` — no suffix, unlike earnings' `_earnings` suffix). Also reuse `_is_reserved` check from `data_store.py:77-78` (`scanner.data_store._is_reserved`) before building any path — every existing cache module guards Windows reserved names at the path-builder or entry-point level; `sector_store.py` must do the same (per CLAUDE.md global convention).

**Core cache-hit / cache-miss / fetch pattern** (`earnings_store.py:27-76`, full `get_earnings_dates` function):
```python
def get_earnings_dates(ticker: str, refresh: bool = False) -> list[date]:
    path = _cache_path(ticker)

    if not refresh and path.exists():
        try:
            df = pd.read_parquet(path)
            return [...]
        except Exception:
            pass

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        def _fetch():
            return yf.Ticker(ticker).get_earnings_dates(limit=60)

        df_raw = fetch_with_retry(_fetch)
        # ... parse df_raw into desired shape ...
        df_out = pd.DataFrame({"date": [...]})
        df_out.to_parquet(path)
        return dates

    except Exception as exc:
        _log.warning("get_earnings_dates: %s failed: %s", ticker, exc)
        # Cache empty so we don't retry every call
        try:
            pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]")}).to_parquet(path)
        except Exception:
            pass
        return []
```
For `sector_store.py`'s `get_sector(ticker, refresh=False) -> Optional[str]`:
- Cache-hit branch: read Parquet, return the single stored `sector` string (or `None` if the cached value is the empty-cache sentinel).
- Cache-miss branch: `yf.Ticker(ticker).info.get("sector")` wrapped in `fetch_with_retry` (per Claude's-discretion note in D-07 — follow `earnings_store.py`'s retry discipline).
- On success with a resolved sector: write a one-row (or one-cell) Parquet with the sector string, return it.
- On failure or unresolved sector (D-03: skip silently, not an error): write an **empty-cache sentinel** exactly like `earnings_store.py:73` (`pd.DataFrame({"sector": pd.Series([], dtype="object")}).to_parquet(path)`) so repeated calls don't retry every run, and return `None`.
- Log at `_log.warning` level on fetch failure, same call shape as `earnings_store.py:70`.

**Reuse directly (no reimplementation):**
- `fetch_with_retry` from `scanner/data_store.py:51-63` — import exactly as `earnings_store.py:16` does: `from scanner.data_store import fetch_with_retry`.
- `_is_reserved` from `scanner/data_store.py:77-78` — import as `from scanner.data_store import _is_reserved` and guard `_cache_path`/`get_sector` entry the same way `data_store.py:224-225` guards `get_history`.

---

### `scanner/seasonality.py` (new pipeline module — name per Claude's discretion, D-04)

**Analog 1 (module shape):** `scan.py` is thin, `scanner/backtest.py` holds the logic — `seasonality_by_week.py` (root) must be thin like `scan.py`, and `scanner/seasonality.py` must hold the sector-resolution + universe-filtering + history-validation logic like `backtest.py` holds `generate_signals`.

**Analog 2 (skip-and-log loop over a universe, non-fatal per-ticker failures):** `scanner/universe.py:90-109` `audit_universe`:
```python
def audit_universe(file_path) -> dict:
    """
    Returns dict with keys 'ok', 'failed' (list of (ticker, error) tuples).
    Failed tickers are non-fatal — the rest of the universe is unaffected.
    """
    from scanner.data_store import refresh_universe

    lines = Path(file_path).read_text(encoding="utf-8").splitlines()
    tickers = [
        l.strip().upper()
        for l in lines
        if l.strip() and not l.startswith("#")
    ]

    _log.info("Auditing %d tickers from %s...", len(tickers), file_path)
    report = refresh_universe(tickers, pause=0.1)

    return {
        "ok": report.succeeded + report.invalidated,
        "failed": report.failed,
    }
```
Copy this "collect a `(ok: list, failed/skipped: list[tuple[ticker, reason]])` report" shape for the new pipeline function (e.g. `resolve_sector_universe(sector, universe_tickers) -> tuple[list[str], list[tuple[str, str]]]` and `validate_history(tickers) -> tuple[dict[str, pd.DataFrame], list[tuple[str, str]]]`). Each stage logs and skips a bad ticker, never raises for a single-ticker failure (SKIP-not-fail philosophy, D-03/D-06).

**Universe resolution — reuse directly, no changes:**
`scanner/universe.py:112-120`:
```python
def load_universe_file(path: Path) -> list[str]:
    """Read a universe text file (# comment lines ignored)."""
    from scanner.data_store import _is_reserved
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [
        l.strip().upper()
        for l in lines
        if l.strip() and not l.startswith("#") and not _is_reserved(l.strip().upper())
    ]
```
`seasonality.py` resolves `--universe` (`sp400`/`sp500`/`sp600`/`all`) to a path (`universes/{name}.txt` or `universes/sp_all.txt`) and calls `load_universe_file(path)` as-is — no reimplementation, no changes needed (per code_context "Reusable Assets").

**Sector-name validation source — reuse directly:**
`scanner/core.py:51-63` `SECTOR_ETF_MAP` (11-entry dict, keys are the canonical GICS sector strings):
```python
SECTOR_ETF_MAP = {
    "Technology":             "XLK",
    "Financial Services":     "XLF",
    "Healthcare":             "XLV",
    "Consumer Cyclical":      "XLY",
    "Communication Services": "XLC",
    "Industrials":            "XLI",
    "Consumer Defensive":     "XLP",
    "Energy":                 "XLE",
    "Utilities":              "XLU",
    "Real Estate":            "XLRE",
    "Basic Materials":        "XLB",
}
```
For SEAS-02 validation: `from scanner.core import SECTOR_ETF_MAP`, validate `--sector` case-insensitively against `SECTOR_ETF_MAP.keys()` (e.g. build a lowercase lookup dict once), and on mismatch raise/print an error listing the 11 valid names verbatim from this dict — do not hardcode a second list (D-02).

**History validation — layer on top of, don't reimplement:**
`scanner/data_store.py:218-242` `get_history`:
```python
def get_history(
    ticker: str,
    end: date | None = None,
    refresh: bool = False,
) -> pd.DataFrame | None:
    """Return cached daily OHLCV, optionally sliced to end date."""
    if _is_reserved(ticker):
        return None
    if refresh:
        try:
            refresh_ticker(ticker)
        except Exception:
            pass

    df = _read_cache(ticker)
    if df is None:
        try:
            df = _do_full_fetch(ticker)
        except Exception:
            return None

    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]

    return df if len(df) >= _MIN_ROWS else None
```
`seasonality.py`'s history-validation step: call `get_history(ticker)` as-is (already enforces the 220-row / `_MIN_ROWS` floor and returns `None` on any failure/insufficiency — D-06's "lower floor"). Then apply Phase 5's own explicit ≥2-year check on the returned DataFrame's date span (D-05: measured against raw cached history, independent of `--years`) before admitting the ticker. If `get_history` returns `None` or the 2-year check fails, skip-and-log via the `audit_universe`-style report shape above — never abort the run for one ticker.

---

### `seasonality_by_week.py` (new, repo root — thin CLI wrapper)

**Analog:** `scan.py` overall structure (761 lines — do not mirror its full multi-subcommand complexity; only the "thin wrapper delegates to scanner/*.py" convention applies). Representative excerpt of the delegation pattern, `scan.py:249-266` (`cmd_refresh`):
```python
def cmd_refresh(args) -> None:
    from scanner.data_store import refresh_universe
    tickers = _resolve_tickers(args)
    ...
    report = refresh_universe(tickers)
    print(f"Refresh complete: {len(report.succeeded)} ok, "
          f"{len(report.invalidated)} invalidated, {len(report.failed)} failed.")
    for t, err in report.failed:
        print(f"  FAILED: {t}: {err}", file=sys.stderr)
```
`seasonality_by_week.py` should follow the same shape: `argparse` block defining `--sector`, `--universe`, `--years`, `--output`, `--bootstrap-iters`, `--seed` (per PROJECT.md flag list — output/bootstrap flags are Phase 6/7 but the CLI surface may be declared now per Claude's discretion on scope), then a single dispatch function that imports from `scanner.seasonality` and prints/logs the report — no gate/scoring/business logic inline in this file, exactly as `scan.py` never contains gate logic itself (that lives in `scanner/strategies/*.py`).

---

## Shared Patterns

### Retry wrapper for yfinance calls
**Source:** `scanner/data_store.py:51-63` `fetch_with_retry`
**Apply to:** `scanner/sector_store.py`'s `yf.Ticker(ticker).info` fetch (and any other new yfinance call added in this phase)
```python
def fetch_with_retry(fn, *args, retries: int = 3, base_delay: float = 1.0, **kwargs):
    """Call fn(*args, **kwargs) up to `retries` times with exponential back-off."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                _log.warning("fetch_with_retry: attempt %d failed: %s", attempt + 1, exc)
                sleep_sec = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(sleep_sec)
    raise last_exc
```
Import, do not reimplement: `from scanner.data_store import fetch_with_retry`.

### Windows reserved-name guard
**Source:** `scanner/data_store.py:70-78` (`_WIN_RESERVED` frozenset + `_is_reserved`)
**Apply to:** `scanner/sector_store.py._cache_path` / `get_sector` entry point, and any ticker-list filtering in `scanner/seasonality.py` (already handled once by `load_universe_file`, but guard again at any new cache-path builder per CLAUDE.md's "blocked in every data_store entry point" convention).
```python
def _is_reserved(ticker: str) -> bool:
    return ticker.upper() in _WIN_RESERVED
```
Import: `from scanner.data_store import _is_reserved`.

### SKIP-not-fail philosophy for missing/ambiguous data
**Source pattern (conceptual, not a single function):** weekly-missing-data gate and earnings-unknown gate in `scanner/core.py`/strategy evaluators; concretely mirrored in `scanner/universe.py:90-109` (`audit_universe`'s `ok`/`failed` report shape) and `scanner/earnings_store.py:69-76` (empty-cache-on-failure so retries don't storm).
**Apply to:** `sector_store.get_sector` (unresolvable sector → `None`, cache the empty sentinel, no exception raised), `scanner/seasonality.py`'s per-stage filtering (unresolvable sector, insufficient history → log + skip, collect into a `skipped: list[tuple[str, str]]`, continue to next ticker — never let one bad ticker abort the batch).

### Thin-CLI / logic-in-scanner-module convention
**Source:** `scan.py` (root, thin dispatcher) delegating to `scanner/backtest.py`, `scanner/report.py`, `scanner/targets.py`, etc.
**Apply to:** `seasonality_by_week.py` (root) delegating to `scanner/seasonality.py`. No gate/statistics/business logic should live in the root script.

## No Analog Found

None — all three new files have a clear structural analog in the existing codebase (see table above). No RESEARCH.md existed for this phase; CONTEXT.md's canonical_refs and code_context sections fully named the analogs, matching what was found by direct inspection.

## Metadata

**Analog search scope:** `scanner/earnings_store.py`, `scanner/data_store.py`, `scanner/universe.py`, `scanner/core.py`, `scanner/backtest.py`, `scan.py` — all directly named in CONTEXT.md's canonical_refs; no broader glob/grep search was needed since the phase's own context already pinpointed exact files and line numbers.
**Files scanned:** 6 (all read directly or via targeted grep/offset reads)
**Pattern extraction date:** 2026-07-09
