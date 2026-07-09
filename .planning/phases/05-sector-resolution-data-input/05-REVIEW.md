---
phase: 05-sector-resolution-data-input
reviewed: 2026-07-09T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - scanner/sector_store.py
  - tests/test_sector_store.py
  - scanner/seasonality.py
  - tests/test_seasonality.py
  - seasonality_by_week.py
  - tests/test_seasonality_cli.py
findings:
  critical: 0
  warning: 4
  info: 2
  total: 6
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-07-09
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the Phase 5 sector-resolution and seasonality data-input pipeline: `scanner/sector_store.py`
(Parquet-cached ticker→GICS-sector lookup), `scanner/seasonality.py` (sector/universe/history
resolution pipeline), and the thin CLI wrapper `seasonality_by_week.py`, plus their test suites.

The code closely mirrors the existing `earnings_store.py` / `audit_universe` / `scan.py` patterns as
directed by `05-PATTERNS.md`, correctly reuses `fetch_with_retry` and `_is_reserved` from
`data_store.py`, and the skip-not-fail philosophy (D-03/D-06) is implemented consistently and is
well covered by tests. No hardcoded secrets, no `eval`/injection surfaces, no crashes found in the
paths exercised by the shipped tests.

No Critical/blocker-level issues found. Four Warning-level correctness/robustness gaps were found,
concentrated around missing input validation for `--years` (which can silently admit
empty/near-empty "validated" history frames — a violation of the D-05 admission invariant), an
error-handling edge case in `sector_store.get_sector` where a successful fetch can be discarded on
a cache-write failure, unsanitized ticker strings reaching filesystem paths, and an unhandled
exception class in the CLI's error boundary. Two Info-level items are noted for completeness.

## Warnings

### WR-01: `--years <= 0` (or absurdly large) silently produces invalid "admitted" data instead of a validation error

**File:** `scanner/seasonality.py:136-138`, `seasonality_by_week.py:38-41`

**Issue:** `validate_history()` trims an admitted frame with:
```python
if years is not None:
    cutoff = df.index.max() - pd.DateOffset(years=years)
    df = df[df.index >= cutoff]
```
`--years` is declared as a plain `type=int` argparse flag with no lower bound (`seasonality_by_week.py:38-41`) and `validate_history()` performs no range check. Two concrete failure modes:

- `--years 0` → `cutoff == df.index.max()`, so the "admitted" frame is trimmed down to essentially a single day. The ticker is still counted as admitted (`frames[ticker] = df`), silently violating the stated invariant in `05-CONTEXT.md` D-05 that admission means "≥2 years of history" — the *raw* check passed, but the frame handed to downstream analysis is empty of useful data.
- `--years -5` → `df.index.max() - pd.DateOffset(years=-5)` computes a cutoff **5 years in the future**, so `df.index >= cutoff` matches nothing and `frames[ticker]` becomes a genuinely **empty DataFrame** that is still reported as "admitted" in the CLI summary (`Admitted: N`), not as skipped. Nothing downstream is told this ticker has 0 rows.
- A very large `--years` (e.g. `9999`) can push `df.index.max() - pd.DateOffset(years=9999)` outside pandas' nanosecond `Timestamp` bounds, raising `OutOfBoundsDatetime`. This is swallowed by the per-ticker `except Exception` at line 141-143 and reported as `(ticker, "error")` for every ticker in the universe, with no top-level message telling the user *why* every ticker failed.

**Fix:** Validate `years` once, either in `build_parser()` (e.g. reject non-positive ints) or at the top of `validate_history()` / `load_sector_dataset()`:
```python
if years is not None and years <= 0:
    raise ValueError(f"--years must be a positive integer, got {years}")
```
and let `main()`'s existing `except ValueError` handle the friendly CLI message.

### WR-02: `get_sector()` discards a successfully-fetched sector if the cache write fails

**File:** `scanner/sector_store.py:50-74`

**Issue:** The Parquet write for a successful fetch happens inside the same `try` block whose `except Exception` (line 67) is meant to handle *fetch* failures:
```python
try:
    ...
    sector = fetch_with_retry(_fetch)
    if sector:
        pd.DataFrame({"sector": [sector]}).to_parquet(path)   # line 57
        return sector
    ...
except Exception as exc:
    _log.warning("get_sector: %s failed: %s", ticker, exc)
    ...
    return None
```
If `to_parquet` raises (disk full, permission denied, locked file on Windows, etc.) *after* a successful network fetch, the exception is caught by the same handler used for fetch failures, the correctly-resolved `sector` value is thrown away, and the function returns `None` — indistinguishable from "yfinance has no sector for this ticker". The caller (`resolve_sector_universe`) will then treat a perfectly resolvable ticker as `unresolved-sector` and drop it from the analysis, and worse, the log message ("get_sector: %s failed: %s") misleadingly implies the *fetch* failed.

**Fix:** Return the resolved `sector` even if caching fails; only best-effort the persistence:
```python
if sector:
    try:
        pd.DataFrame({"sector": [sector]}).to_parquet(path)
    except Exception as write_exc:
        _log.warning("get_sector: cache write failed for %s: %s", ticker, write_exc)
    return sector
```

### WR-03: Ticker string is not sanitized before being used in a filesystem path

**File:** `scanner/sector_store.py:23-24`, `34-37`

**Issue:** `_cache_path()` builds `_CACHE_DIR / f"{ticker.upper()}.parquet"` directly from the caller-supplied `ticker`. The only guard applied is the Windows-reserved-device-name check (`_is_reserved`); there is no allowlist for path-separator or `..`-traversal characters. In the current call graph this is unreachable because the only caller (`seasonality.resolve_sector_universe`) sources tickers from `load_universe_file()`, which reads a fixed, repo-tracked universe file — so it is not exploitable today. However `get_sector()` is a public module-level function with no such guarantee documented or enforced for any future caller (e.g. a web API endpoint or ad-hoc script passing a user-supplied ticker), and this is exactly the class of bug CLAUDE.md's Windows-reserved-name convention was written to prevent for cache paths in general.

**Fix:** Validate the ticker against a conservative character allowlist before building the path, e.g.:
```python
import re
_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-]{1,10}$")

def get_sector(ticker: str, refresh: bool = False) -> Optional[str]:
    if _is_reserved(ticker) or not _TICKER_RE.match(ticker):
        return None
    ...
```

### WR-04: CLI error boundary only catches `ValueError`; a missing/unreadable universe file crashes with a raw traceback

**File:** `seasonality_by_week.py:62-66`

**Issue:**
```python
try:
    ds = seasonality.load_sector_dataset(args.sector, args.universe, years=args.years)
except ValueError as exc:
    print(str(exc), file=sys.stderr)
    return 2
```
`load_sector_dataset()` → `load_universe_file(path)` (`scanner/universe.py:115`) does `Path(path).read_text(encoding="utf-8")` with no exception handling. If the whitelisted universe path is missing (e.g. `universes/sp_all.txt` deleted or not yet generated) or unreadable, this raises `FileNotFoundError` / `OSError`, which is not a `ValueError` and is therefore not caught here — the CLI exits with an unhandled traceback instead of a clean error message and exit code, unlike the SEAS-02 sector-validation path which is explicitly designed for graceful failure.

**Fix:** Broaden the CLI's error boundary (or wrap the file read in `seasonality.py`) to convert I/O errors into the same friendly-message path:
```python
except (ValueError, OSError) as exc:
    print(str(exc), file=sys.stderr)
    return 2
```

## Info

### IN-01: `SectorDataset.universe` is not `.strip()`-ed like `sector` is

**File:** `scanner/seasonality.py:167`

**Issue:** `load_sector_dataset()` canonicalizes `sector` fully via `resolve_sector()` (which strips and title-cases), but stores `universe=universe.lower()` verbatim — no `.strip()`. If a caller passes `--universe " sp500 "` (extra whitespace), `universe_path()` resolves it correctly (it strips internally), but the `SectorDataset.universe` field displayed to the user retains the untrimmed value, e.g. `" sp500 "`.

**Fix:** `universe=universe.strip().lower()`.

### IN-02: `resolve_sector_universe`'s exception handler around `get_sector` is unreachable/untested

**File:** `scanner/seasonality.py:90-95`

**Issue:** `sector_store.get_sector()` is documented and implemented to never raise — every internal failure path returns `None`. The `try/except Exception` wrapped around the call in `resolve_sector_universe` is therefore defensive dead code under the current contract, and no test in `test_seasonality.py` exercises it (all sector-resolution tests use a fake `get_sector` that returns a value or `None`, never raises). This isn't wrong, but if `get_sector`'s contract ever changes to raise for some error class, this branch would silently mask that as a generic `"unresolved-sector"` skip with no visibility into the fact that a real exception occurred versus normal "not found" behavior.

**Fix:** Either add a test that monkeypatches `get_sector` to raise (to lock in the intended behavior), or drop the redundant try/except and let `get_sector`'s documented "always returns `Optional[str]`, never raises" contract stand on its own.

---

_Reviewed: 2026-07-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
